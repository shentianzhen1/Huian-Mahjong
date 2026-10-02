import copy
import json
from pathlib import Path
import unittest

from workspace.vision.issue69_hand1_replay_audit import audit_hand1_timeline

ROOT = Path(__file__).resolve().parents[1]
TIMELINE = ROOT / "references/vision/2026-10-02/issue69_hand1_machine_timeline_v0_1.json"


class Issue69Hand1ReplayAuditTests(unittest.TestCase):
    def load(self):
        return json.loads(TIMELINE.read_text(encoding="utf-8"))

    def test_current_hand1_fixture_passes_integrity_audit(self):
        report = audit_hand1_timeline(self.load())
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["event_count"], 9)
        self.assertEqual(report["claim_event_count"], 2)
        self.assertTrue(report["youjin_terminal_present"])
        self.assertFalse(report["safe_for_runtime"])

    def test_duplicate_or_gap_order_fails(self):
        data = self.load()
        data["events"][3]["order"] = 3
        self.assertIn("EVENT_ORDER_NOT_CONTIGUOUS", audit_hand1_timeline(data)["errors"])

    def test_cross_match_event_fails(self):
        data = self.load()
        data["events"][4]["original_match_group"] = "another_match"
        self.assertIn("MATCH_GROUP_SCOPE_MISMATCH", audit_hand1_timeline(data)["errors"])

    def test_claimed_discard_must_transfer_into_meld(self):
        data = self.load()
        data["events"][2]["human_reviewed_truth"]["player_discard"] = "P9"
        self.assertIn(
            "CLAIMED_DISCARD_NOT_CONSUMED_BY_MELD",
            audit_hand1_timeline(data)["errors"],
        )

    def test_youjin_response_discard_cannot_be_skipped(self):
        data = self.load()
        chain = data["events"][8]["reviewed_rule_chain"]
        chain.remove("OPPONENT_MANDATORY_DISCARD_M3")
        self.assertIn("YOUJIN_RESPONSE_CHAIN_INVALID", audit_hand1_timeline(data)["errors"])

    def test_settlement_arithmetic_drift_fails(self):
        data = self.load()
        data["events"][8]["settlement"]["net_score"] = 67
        self.assertIn(
            "YOUJIN_SETTLEMENT_ARITHMETIC_MISMATCH",
            audit_hand1_timeline(data)["errors"],
        )

    def test_machine_promotion_stays_forbidden(self):
        data = self.load()
        data["events"][0]["machine_confirmed"] = True
        errors = audit_hand1_timeline(data)["errors"]
        self.assertIn("MACHINE_CLOSED_COUNT_MISMATCH", errors)
        self.assertIn("UNEXPECTED_MACHINE_PROMOTION", errors)


if __name__ == "__main__":
    unittest.main()
