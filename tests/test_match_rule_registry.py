import unittest

from huian.rules.registry import DEFAULT_RULE_SNAPSHOT


class MatchRuleRegistryTests(unittest.TestCase):
    def test_player_confirmed_dealer_flow_is_source_agnostic(self):
        rule = DEFAULT_RULE_SNAPSHOT.require_confirmed(
            "match.normal_dealer_flow"
        )
        self.assertEqual(rule.value, {
            "scope": "ALL_HU_METHODS",
            "dealer_win": "STAY_AND_ADD_5",
            "draw": "STAY_AND_ADD_5",
            "nondealer_win": "SWITCH_AND_RESET_10",
        })
        self.assertEqual(
            rule.depends_on,
            ("match.new_dealer_base", "match.repeat_dealer_increment"),
        )
        self.assertIn(
            "player_confirmed_special_rules_20261006_v1",
            rule.evidence_ids,
        )

    def test_player_confirmed_fixed_eight_hand_tie_has_no_tiebreak(self):
        rule = DEFAULT_RULE_SNAPSHOT.require_confirmed(
            "match.fixed_eight_hand_tie"
        )
        self.assertEqual(rule.value["hand_count"], 8)
        self.assertEqual(rule.value["equal_final_scores"], "TIE")
        self.assertFalse(rule.value["extra_hand"])
        self.assertFalse(rule.value["dealer_tiebreak"])
        self.assertIn(
            "player_confirmed_special_rules_20261006_v1",
            rule.evidence_ids,
        )


if __name__ == "__main__":
    unittest.main()
