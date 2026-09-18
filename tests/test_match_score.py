import unittest

from workspace.simulator import MatchScoreState, score_eight_hand_match


class MatchScoreTests(unittest.TestCase):
    def test_match_starts_1000_each_and_conserves_2000(self):
        state = MatchScoreState.initial()
        self.assertEqual(state.scores, (1000, 1000))
        self.assertEqual(state.hands_played, 0)
        self.assertEqual(state.hands_remaining, 8)
        self.assertEqual(state.margin, 0)
        self.assertFalse(state.complete)

        state = state.apply_hand((11, -11))
        self.assertEqual(state.scores, (1011, 989))
        self.assertEqual(state.margin_for(0), 22)
        self.assertEqual(state.margin_for(1), -22)
        self.assertEqual(sum(state.scores), 2000)

    def test_eight_hand_final_score_is_primary_outcome(self):
        rewards = (
            (11, -11),
            (-20, 20),
            (0, 0),
            (38, -38),
            (-16, 16),
            (5, -5),
            (-8, 8),
            (100, -100),
        )
        state = score_eight_hand_match(rewards)
        self.assertTrue(state.complete)
        self.assertEqual(state.hands_played, 8)
        self.assertEqual(state.hands_remaining, 0)
        self.assertEqual(state.scores, (1110, 890))
        self.assertEqual(state.margin, 220)
        self.assertEqual(sum(state.scores), 2000)

    def test_same_final_objective_as_accumulated_delta_when_start_equal(self):
        a = score_eight_hand_match(((10, -10),) * 8)
        b = score_eight_hand_match(((5, -5),) * 8)
        self.assertGreater(a.score_for(0), b.score_for(0))
        self.assertGreater(a.margin_for(0), b.margin_for(0))

    def test_rejects_non_zero_sum_or_wrong_match_length(self):
        with self.assertRaises(ValueError):
            MatchScoreState.initial().apply_hand((10, -9))
        with self.assertRaises(ValueError):
            MatchScoreState.initial().apply_hand((True, -1))
        with self.assertRaises(ValueError):
            score_eight_hand_match([(0, 0)] * 7)
        state = score_eight_hand_match([(0, 0)] * 8)
        with self.assertRaises(ValueError):
            state.apply_hand((1, -1))


if __name__ == "__main__":
    unittest.main()
