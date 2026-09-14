import unittest

from huian import HuianEnvironment, UnknownRuleError


class ObservedOutcomeEnvironmentTests(unittest.TestCase):
    def ready_opening(self):
        game = HuianEnvironment()
        game.reset(seed=42)
        game.begin_opening(dice_total=7)
        return game

    def test_pinghu_outcome_is_terminal_zero_sum_and_auditable(self):
        game = self.ready_opening()
        state, event = game.finalize_observed_outcome(
            winner=1, current_dealer_base=15, winner_fan=1, win_type="PINGHU"
        )
        self.assertTrue(state.terminal)
        self.assertEqual(state.terminal_reason, "OBSERVED_PINGHU")
        self.assertEqual(state.rewards, [-16, 16])
        self.assertEqual(event["action"]["metadata"], {
            "source": "observed", "win_type": "PINGHU", "current_dealer_base": 15,
            "winner_fan": 1, "multiplier": 1,
        })
        self.assertEqual(game.get_reward(), [-16, 16])
        self.assertEqual(sum(state.rewards), 0)

    def test_zimo_and_unknown_outcome_handling(self):
        game = self.ready_opening()
        state, _ = game.finalize_observed_outcome(
            winner=0, current_dealer_base=10, winner_fan=9, win_type="ZIMO"
        )
        self.assertEqual(state.rewards, [38, -38])
        with self.assertRaises(ValueError):
            game.finalize_observed_outcome(
                winner=0, current_dealer_base=10, winner_fan=9, win_type="ZIMO"
            )
        blocked = self.ready_opening()
        with self.assertRaises(UnknownRuleError):
            blocked.finalize_observed_outcome(
                winner=0, current_dealer_base=10, winner_fan=1, win_type="QIANGJIN"
            )
        self.assertFalse(blocked.is_terminal())


if __name__ == "__main__":
    unittest.main()