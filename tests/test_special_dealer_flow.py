import unittest

from workspace.simulator import MatchHandResult, run_eight_hand_match


class SpecialDealerFlowTests(unittest.TestCase):
    def test_special_win_source_never_overrides_winner_based_dealer_flow(self):
        scripted = iter((
            ("tianhu", 0),
            ("qiangjin", 1),
            ("eight_flower_you", 1),
            ("sanjindao", 0),
            ("youjin", 0),
            ("double_you", 1),
            ("triple_you", 1),
            ("self_draw", 0),
        ))
        seen = []

        def hand_runner(context):
            seen.append((
                context.hand_index,
                context.dealer,
                context.current_dealer_base,
            ))
            source, winner = next(scripted)
            rewards = (5, -5) if winner == 0 else (-5, 5)
            return MatchHandResult.settled(
                rewards,
                winner=winner,
                terminal_reason="AUTO_SPECIAL",
                win_source=source,
            )

        result = run_eight_hand_match(hand_runner, initial_dealer=0)
        self.assertTrue(result.complete)
        self.assertEqual(
            seen,
            [
                (0, 0, 10),
                (1, 0, 15),
                (2, 1, 10),
                (3, 1, 15),
                (4, 0, 10),
                (5, 0, 15),
                (6, 1, 10),
                (7, 1, 15),
            ],
        )
        self.assertEqual(sum(result.final_scores), 2000)
        self.assertEqual(result.progress.hand_index, 8)
        self.assertEqual(result.win_source_counts, {
            "tianhu": 1,
            "qiangjin": 1,
            "eight_flower_you": 1,
            "sanjindao": 1,
            "youjin": 1,
            "double_you": 1,
            "triple_you": 1,
            "self_draw": 1,
        })


if __name__ == "__main__":
    unittest.main()
