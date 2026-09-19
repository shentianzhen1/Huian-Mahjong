import unittest

from workspace.simulator import MatchProgressState, MatchScoreState, score_eight_hand_match


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

    def test_match_progress_updates_scores_dealer_and_next_base(self):
        match = MatchProgressState.initial(dealer=0)
        self.assertEqual(match.scores, (1000, 1000))
        self.assertEqual(match.current_dealer_base, 20)
        self.assertEqual(match.hand_index, 0)

        # Dealer wins: keep dealer and increase next-hand base by 5.
        match = match.apply_settled_hand((11, -11), winner=0)
        self.assertEqual(match.scores, (1011, 989))
        self.assertEqual(match.dealer, 0)
        self.assertEqual(match.consecutive_dealer_hands, 2)
        self.assertEqual(match.current_dealer_base, 10)

        # Draw: same dealer keeps again and base increases again.
        match = match.apply_settled_hand((0, 0), winner=None)
        self.assertEqual(match.dealer, 0)
        self.assertEqual(match.consecutive_dealer_hands, 3)
        self.assertEqual(match.current_dealer_base, 15)

        # Dealer loses: opponent becomes dealer and settlement base resets to 10.
        match = match.apply_settled_hand((-16, 16), winner=1)
        self.assertEqual(match.scores, (995, 1005))
        self.assertEqual(match.dealer, 1)
        self.assertEqual(match.consecutive_dealer_hands, 1)
        self.assertEqual(match.current_dealer_base, 10)

    def test_room541913_observed_dealer_base_chain(self):
        match = MatchProgressState.initial(dealer=0)
        self.assertEqual((match.dealer, match.current_dealer_base), (0, 10))

        match = match.apply_settled_hand((26, -26), winner=0)
        self.assertEqual((match.dealer, match.current_dealer_base), (0, 15))

        match = match.apply_settled_hand((-68, 68), winner=1)
        self.assertEqual((match.dealer, match.current_dealer_base), (1, 10))

        match = match.apply_settled_hand((22, -22), winner=0)
        self.assertEqual((match.dealer, match.current_dealer_base), (0, 10))

        for reward in ((24, -24), (76, -76), (25, -25)):
            match = match.apply_settled_hand(reward, winner=0)
        self.assertEqual((match.dealer, match.current_dealer_base), (0, 25))

    def test_match_progress_finishes_after_exactly_eight_settled_hands(self):
        match = MatchProgressState.initial(dealer=1)
        for index in range(8):
            winner = None if index % 3 == 0 else match.dealer
            rewards = (0, 0) if winner is None else (
                (5, -5) if winner == 0 else (-5, 5)
            )
            match = match.apply_settled_hand(rewards, winner=winner)
        self.assertTrue(match.complete)
        self.assertEqual(match.hand_index, 8)
        self.assertEqual(match.hands_remaining, 0)
        self.assertEqual(sum(match.scores), 2000)
        with self.assertRaises(ValueError):
            _ = match.current_dealer_base
        with self.assertRaises(ValueError):
            match.apply_settled_hand((1, -1), winner=0)

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
