import unittest

from huian import (
    WinSource,
    YoujinOfferRule,
    YoujinOpponentResponseRule,
    YoujinProgressionRule,
    YoujinStage,
    youjin_offer_rule,
    youjin_opponent_response_rule,
    youjin_progression_rule,
)


class YoujinOpponentResponseRuleTests(unittest.TestCase):

    def test_youjin_offer_is_optional_and_decline_does_not_lock_later_progression(self):
        rule = youjin_offer_rule()
        self.assertIsInstance(rule, YoujinOfferRule)
        self.assertTrue(rule.optional)
        self.assertTrue(rule.decline_keeps_playing)
        self.assertFalse(rule.decline_blocks_later_youjin)

    def test_all_three_stages_share_one_normal_self_draw_interception(self):
        for stage in (
            YoujinStage.YOUJIN,
            YoujinStage.DOUBLE_YOU,
            YoujinStage.TRIPLE_YOU,
        ):
            with self.subTest(stage=stage):
                rule = youjin_opponent_response_rule(stage)
                self.assertIsInstance(rule, YoujinOpponentResponseRule)
                self.assertEqual(rule.stage, stage)
                self.assertEqual(rule.opponent_draw_chances, 1)
                self.assertEqual(rule.allowed_win_sources, (WinSource.SELF_DRAW,))
                self.assertEqual(rule.no_win_outcome, "YOUJIN_STAGE_SUCCESS")

    def test_triple_you_is_not_limited_to_kong_tail_hu(self):
        rule = youjin_opponent_response_rule(YoujinStage.TRIPLE_YOU)
        self.assertIn(WinSource.SELF_DRAW, rule.allowed_win_sources)
        self.assertNotIn(WinSource.KONG_TAIL_DRAW, rule.allowed_win_sources)

    def test_sanjin_you_alias_normalizes_to_triple_you(self):
        rule = youjin_opponent_response_rule(YoujinStage.SANJIN_YOU)
        self.assertEqual(rule.stage, YoujinStage.TRIPLE_YOU)

    def test_normal_stage_has_no_youjin_response_window(self):
        with self.assertRaisesRegex(ValueError, "NORMAL"):
            youjin_opponent_response_rule(YoujinStage.NORMAL)

    def test_single_and_double_survival_get_one_optional_upgrade_draw(self):
        cases = (
            (YoujinStage.YOUJIN, YoujinStage.DOUBLE_YOU),
            (YoujinStage.DOUBLE_YOU, YoujinStage.TRIPLE_YOU),
        )
        for stage, next_stage in cases:
            with self.subTest(stage=stage):
                rule = youjin_progression_rule(stage)
                self.assertIsInstance(rule, YoujinProgressionRule)
                self.assertEqual(rule.youjin_player_draw_chances, 1)
                self.assertEqual(rule.next_stage, next_stage)
                self.assertTrue(rule.upgrade_optional)
                self.assertEqual(rule.opponent_miss_outcome, "YOUJIN_PLAYER_DRAW")
                self.assertEqual(rule.no_upgrade_outcome, "SETTLE_CURRENT_STAGE")

    def test_triple_you_opponent_miss_settles_immediately(self):
        rule = youjin_progression_rule(YoujinStage.TRIPLE_YOU)
        self.assertEqual(rule.youjin_player_draw_chances, 0)
        self.assertIsNone(rule.next_stage)
        self.assertFalse(rule.upgrade_optional)
        self.assertEqual(rule.opponent_miss_outcome, "SETTLE_CURRENT_STAGE")

    def test_normal_has_no_progression_rule(self):
        with self.assertRaisesRegex(ValueError, "NORMAL"):
            youjin_progression_rule(YoujinStage.NORMAL)


if __name__ == "__main__":
    unittest.main()
