import unittest

from huian import HuianRules, SPECIAL_OUTCOMES, YoujinStage, special_outcome_profile
from huian.rules import special_outcome_for_phase, special_outcome_for_source
from huian.rules import EvidenceStatus


class SpecialOutcomeRegistryTests(unittest.TestCase):
    def test_qiangjin_is_player_confirmed_first_round_normal_zimo_settlement(self):
        profile = special_outcome_profile("QIANGJIN")
        self.assertEqual(profile.multiplier, 2)
        self.assertEqual(profile.multiplier_status, EvidenceStatus.CONFIRMED)
        self.assertTrue(profile.settlement_ready)
        self.assertEqual(profile.settlement_rule_id, "settlement.qiangjin_full")
        self.assertEqual(profile.action_metadata["multiplier"], 2)
        self.assertEqual(profile.action_metadata["multiplier_evidence"], "CONFIRMED")

    def test_confirmed_and_project_multipliers_are_distinguished(self):
        sanjindao = special_outcome_profile("SANJINDAO")
        self.assertEqual(sanjindao.multiplier, 3)
        self.assertEqual(sanjindao.multiplier_status, EvidenceStatus.CONFIRMED)
        self.assertTrue(sanjindao.settlement_ready)

        eight = special_outcome_profile("EIGHT_FLOWER_YOU")
        self.assertEqual(eight.multiplier, 1)
        self.assertEqual(eight.fixed_fan, 16)
        self.assertEqual(eight.multiplier_status, EvidenceStatus.CONFIRMED)
        self.assertTrue(eight.settlement_ready)
        self.assertFalse(eight.project_rule)
        self.assertEqual(eight.action_metadata["fixed_fan"], 16)

        youjin = special_outcome_profile("YOUJIN")
        self.assertEqual(youjin.multiplier, 4)
        self.assertEqual(youjin.multiplier_status, EvidenceStatus.CONFIRMED)

        double_you = special_outcome_profile("DOUBLE_YOU")
        self.assertEqual(double_you.multiplier, 8)
        self.assertEqual(double_you.multiplier_status, EvidenceStatus.CONFIRMED)
        self.assertFalse(double_you.settlement_ready)

        triple_you = special_outcome_profile("TRIPLE_YOU")
        self.assertEqual(triple_you.multiplier, 16)
        self.assertEqual(triple_you.multiplier_status, EvidenceStatus.CONFIRMED)

        rob_kong = special_outcome_profile("ROB_KONG_HU")
        self.assertEqual(rob_kong.multiplier, 2)
        self.assertEqual(rob_kong.multiplier_status, EvidenceStatus.CONFIRMED)
        self.assertTrue(rob_kong.settlement_ready)
        self.assertIsNone(rob_kong.settlement_rule_id)

    def test_phase_and_source_lookup_agree_for_declared_specials(self):
        # QIANGJIN_DECLARED remains readable for historical/imported evidence;
        # new staged runtime Qiangjin settles atomically from first_round facts.
        self.assertEqual(
            special_outcome_for_phase("QIANGJIN_DECLARED").key, "QIANGJIN")
        self.assertEqual(
            special_outcome_for_source("qiangjin").key, "QIANGJIN")
        self.assertEqual(
            special_outcome_for_phase("SANJINDAO_DECLARED").key, "SANJINDAO")
        self.assertEqual(
            special_outcome_for_source("sanjindao").key, "SANJINDAO")

    def test_rules_read_special_multipliers_from_registry(self):
        self.assertEqual(
            HuianRules.SANJINDAO_MULTIPLIER,
            special_outcome_profile("SANJINDAO").multiplier,
        )
        self.assertEqual(
            HuianRules.YOUJIN_MULTIPLIERS[YoujinStage.YOUJIN],
            special_outcome_profile("YOUJIN").multiplier,
        )
        self.assertEqual(
            HuianRules.YOUJIN_MULTIPLIERS[YoujinStage.DOUBLE_YOU],
            special_outcome_profile("DOUBLE_YOU").multiplier,
        )
        self.assertEqual(
            HuianRules.YOUJIN_MULTIPLIERS[YoujinStage.TRIPLE_YOU],
            special_outcome_profile("TRIPLE_YOU").multiplier,
        )

    def test_registry_is_read_only_and_rejects_unknown_keys(self):
        with self.assertRaises(TypeError):
            SPECIAL_OUTCOMES["BAD"] = None
        with self.assertRaises(ValueError):
            special_outcome_profile("BAD")


if __name__ == "__main__":
    unittest.main()
