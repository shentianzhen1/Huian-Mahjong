import json
from tempfile import TemporaryDirectory
import unittest
from types import SimpleNamespace

from huian.rules import DEFAULT_RULE_SNAPSHOT
from huian.version import PROJECT_VERSION, project_manifest
from workspace.ai import CURRENT_AGENT_VERSION
from workspace.hint_alpha import (
    AdvisoryGate,
    AdvisoryState,
    EvidenceSession,
    FanBreakdownItem,
    HintAdvisor,
    ObservedSettlement,
    SettlementPrediction,
    audit_settlement,
)


class FakeImage:
    def save(self, path, format=None):
        path.write_bytes(b"fake-png")


class HintAlphaSafetyTests(unittest.TestCase):
    def test_gate_fails_closed_for_vision_and_unknown_rules(self):
        gate = AdvisoryGate(minimum_vision_confidence=0.80)
        self.assertEqual(
            gate.evaluate(vision_confidence=None).state,
            AdvisoryState.VISION_PENDING,
        )
        low = gate.evaluate(vision_confidence=0.79)
        self.assertFalse(low.allowed)
        self.assertEqual(low.state, AdvisoryState.VISION_UNTRUSTED)

        unknown = gate.evaluate(
            vision_confidence=0.99,
            unresolved_rules=("settlement.gang_hu",),
        )
        self.assertEqual(unknown.state, AdvisoryState.RULE_UNKNOWN)

        working = gate.evaluate(
            vision_confidence=0.99,
            required_rules=("settlement.eight_flower_working_fixed_fan",),
        )
        self.assertEqual(working.state, AdvisoryState.RULE_NOT_CONFIRMED)

    def test_confirmed_path_can_reach_advisor(self):
        fake_action = SimpleNamespace(
            type=SimpleNamespace(value="DISCARD"),
            tile="M1",
        )
        fake_agent = SimpleNamespace(
            choose_decision=lambda observation, actions: SimpleNamespace(
                action=actions[0], reason="test decision"
            )
        )
        advisor = HintAdvisor(agent=fake_agent)
        result = advisor.recommend(
            object(),
            (fake_action,),
            vision_confidence=0.95,
            required_rules=("match.new_dealer_base",),
        )
        self.assertTrue(result.allowed)
        self.assertEqual((result.action_type, result.tile), ("DISCARD", "M1"))
        self.assertEqual(result.rule_snapshot_id, DEFAULT_RULE_SNAPSHOT.fingerprint)


class HintAlphaEvidenceTests(unittest.TestCase):
    def test_session_keeps_rule_and_agent_provenance(self):
        with TemporaryDirectory() as root:
            session = EvidenceSession(root, metadata={"test": True}, session_id="case")
            frame = session.save_frame(FakeImage(), "recognition_error")
            session.mark_feedback(
                "RECOGNITION_ERROR",
                payload={"frame": str(frame.relative_to(session.path))},
            )
            completion = session.close("test")

            manifest = json.loads((session.path / "session.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["project"], project_manifest())
            self.assertEqual(
                manifest["rule_snapshot"]["fingerprint"],
                DEFAULT_RULE_SNAPSHOT.fingerprint,
            )
            self.assertEqual(manifest["agent"]["version"], CURRENT_AGENT_VERSION)
            self.assertTrue(frame.exists())
            events = [
                json.loads(line)
                for line in (session.path / "events.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            self.assertEqual(
                [item["kind"] for item in events],
                ["SESSION_STARTED", "FRAME_SAVED", "RECOGNITION_ERROR"],
            )
            self.assertEqual(completion["events_written"], 3)
            self.assertEqual(completion["project_version"], PROJECT_VERSION)
            self.assertTrue((session.path / "completion.json").exists())


class SettlementAuditTests(unittest.TestCase):
    def prediction(self):
        return SettlementPrediction(
            current_dealer_base=20,
            fan_total=5,
            multiplier=4,
            fan_breakdown=(
                FanBreakdownItem("金", 2, "fan.gold"),
                FanBreakdownItem("花", 3, "fan.flower"),
            ),
            outcome="YOUJIN",
        )

    def test_exact_match_checks_fan_multiplier_and_net(self):
        result = audit_settlement(
            self.prediction(),
            ObservedSettlement(
                winner=0,
                scores_before=(1000, 1000),
                scores_after=(1100, 900),
                displayed_fan=5,
                displayed_multiplier=4,
            ),
        )
        self.assertEqual(result.status, "MATCH")
        self.assertTrue(result.net_match)
        self.assertTrue(result.fan_match)
        self.assertTrue(result.multiplier_match)

    def test_mismatch_is_explained(self):
        result = audit_settlement(
            self.prediction(),
            ObservedSettlement(
                winner=0,
                scores_before=(1000, 1000),
                scores_after=(1092, 908),
                displayed_fan=3,
                displayed_multiplier=4,
            ),
        )
        self.assertEqual(result.status, "MISMATCH")
        self.assertFalse(result.net_match)
        self.assertFalse(result.fan_match)
        self.assertIn("净分预测100，实际92", result.differences)
        self.assertIn("番数预测5，界面3", result.differences)

    def test_unknown_rule_never_claims_audit_match(self):
        result = audit_settlement(
            self.prediction(),
            ObservedSettlement(
                winner=0,
                scores_before=(1000, 1000),
                scores_after=(1100, 900),
            ),
            unresolved_rules=("settlement.gang_hu",),
        )
        self.assertEqual(result.status, "UNSUPPORTED")
        self.assertIsNone(result.net_match)


if __name__ == "__main__":
    unittest.main()
