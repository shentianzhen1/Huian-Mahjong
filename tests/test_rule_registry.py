import json
import unittest

from huian.rules import EvidenceStatus, HuianRules, RulesConfig
from huian.rules.dealer_base import REPEAT_DEALER_INCREMENT, SITTING_DEALER_BASE
from huian.rules.registry import (
    DEFAULT_RULE_SNAPSHOT,
    ImpactLevel,
    RuleNotConfirmedError,
    RuleSnapshot,
)
from huian.rules.special_outcomes import special_outcome_profile


class RuleRegistryTests(unittest.TestCase):
    def test_snapshot_is_stable_and_json_serializable(self):
        manifest = DEFAULT_RULE_SNAPSHOT.to_manifest()
        self.assertEqual(manifest["fingerprint"], DEFAULT_RULE_SNAPSHOT.fingerprint)
        self.assertEqual(len(DEFAULT_RULE_SNAPSHOT.fingerprint), 64)
        json.dumps(manifest, ensure_ascii=False, sort_keys=True)

        reversed_snapshot = RuleSnapshot(
            label="reordered",
            records=dict(reversed(tuple(DEFAULT_RULE_SNAPSHOT.records.items()))),
        )
        self.assertEqual(
            reversed_snapshot.fingerprint,
            DEFAULT_RULE_SNAPSHOT.fingerprint,
        )

    def test_research_override_is_isolated_and_changes_fingerprint(self):
        original = DEFAULT_RULE_SNAPSHOT.get("settlement.gang_hu")
        experimental = DEFAULT_RULE_SNAPSHOT.with_overrides(
            label="research-only",
            overrides={
                "settlement.gang_hu": {
                    "status": EvidenceStatus.WORKING,
                    "revision": original.revision + 1,
                    "value": {"multiplier": 2},
                    "impact": ImpactLevel.CRITICAL,
                    "note": "test-only override",
                }
            },
        )
        self.assertIsNone(DEFAULT_RULE_SNAPSHOT.get("settlement.gang_hu").value)
        self.assertEqual(
            DEFAULT_RULE_SNAPSHOT.get("settlement.gang_hu").status,
            EvidenceStatus.UNKNOWN,
        )
        self.assertNotEqual(experimental.fingerprint, DEFAULT_RULE_SNAPSHOT.fingerprint)
        self.assertEqual(experimental.get("settlement.gang_hu").value, {"multiplier": 2})

    def test_confirmed_gate_rejects_working_and_unknown(self):
        confirmed = DEFAULT_RULE_SNAPSHOT.require_confirmed(
            "settlement.youjin_multiplier"
        )
        self.assertEqual(confirmed.value, 4)
        for rule_id in (
            "settlement.gang_hu",
            "settlement.eight_flower_working_fixed_fan",
        ):
            with self.subTest(rule_id=rule_id):
                with self.assertRaises(RuleNotConfirmedError):
                    DEFAULT_RULE_SNAPSHOT.require_confirmed(rule_id)

    def test_registry_matches_current_high_impact_runtime_constants(self):
        self.assertEqual(
            DEFAULT_RULE_SNAPSHOT.require_confirmed(
                "match.new_dealer_base"
            ).value,
            SITTING_DEALER_BASE,
        )
        self.assertEqual(
            DEFAULT_RULE_SNAPSHOT.require_confirmed(
                "match.repeat_dealer_increment"
            ).value,
            REPEAT_DEALER_INCREMENT,
        )
        expected = {
            "YOUJIN": ("settlement.youjin_multiplier", 4),
            "DOUBLE_YOU": ("settlement.double_you_multiplier", 8),
            "TRIPLE_YOU": ("settlement.triple_you_multiplier", 16),
            "ROB_KONG_HU": ("settlement.rob_kong_multiplier", 2),
            "SANJINDAO": ("settlement.sanjindao_multiplier", 3),
        }
        for outcome, (rule_id, multiplier) in expected.items():
            with self.subTest(outcome=outcome):
                self.assertEqual(
                    DEFAULT_RULE_SNAPSHOT.require_confirmed(rule_id).value,
                    multiplier,
                )
                self.assertEqual(
                    special_outcome_profile(outcome).multiplier,
                    multiplier,
                )

    def test_target_room_defaults_match_registry(self):
        self.assertEqual(
            RulesConfig().single_gold_can_pinghu,
            DEFAULT_RULE_SNAPSHOT.require_confirmed(
                "legality.single_gold_discard_pinghu"
            ).value,
        )
        self.assertEqual(
            HuianRules.MAX_PLAYABLE_GOLD_COPIES,
            DEFAULT_RULE_SNAPSHOT.require_confirmed(
                "physical.max_playable_gold_copies"
            ).value,
        )

    def test_unknown_dependencies_are_explicit(self):
        robbed = DEFAULT_RULE_SNAPSHOT.get("settlement.rob_kong_full")
        self.assertEqual(robbed.status, EvidenceStatus.UNKNOWN)
        self.assertEqual(
            robbed.depends_on,
            ("legality.rob_kong_scope", "settlement.rob_kong_multiplier"),
        )


if __name__ == "__main__":
    unittest.main()
