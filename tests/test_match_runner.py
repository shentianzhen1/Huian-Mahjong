import unittest

from huian import UnknownRuleError
from workspace.simulator import (
    MatchHandResult, MatchRunner, run_eight_hand_match,
)


class MatchRunnerTests(unittest.TestCase):
    def test_full_eight_hand_runner_updates_context_and_final_scores(self):
        seen = []

        def hand_runner(context):
            seen.append(context)
            # Hand 0 dealer wins, hand 1 draws, hand 2 dealer loses.
            # Remaining hands are wins by the current dealer.
            if context.hand_index == 0:
                return MatchHandResult.settled((11, -11), winner=0,
                                               terminal_reason="AUTO_PINGHU")
            if context.hand_index == 1:
                return MatchHandResult.settled((0, 0), winner=None,
                                               terminal_reason="WALL_16")
            if context.hand_index == 2:
                return MatchHandResult.settled((-16, 16), winner=1,
                                               terminal_reason="AUTO_PINGHU")
            reward = (5, -5) if context.dealer == 0 else (-5, 5)
            return MatchHandResult.settled(
                reward, winner=context.dealer, terminal_reason="AUTO_PINGHU")

        result = run_eight_hand_match(hand_runner, initial_dealer=0)
        self.assertTrue(result.complete)
        self.assertEqual(len(result.hands), 8)
        self.assertEqual(result.progress.hand_index, 8)
        self.assertEqual(result.final_scores, (970, 1030))
        self.assertEqual(sum(result.final_scores), 2000)

        self.assertEqual(
            [(c.hand_index, c.dealer, c.current_dealer_base) for c in seen[:4]],
            [(0, 0, 5), (1, 0, 10), (2, 0, 15), (3, 1, 5)],
        )
        self.assertEqual(seen[0].scores, (1000, 1000))
        self.assertEqual(seen[1].scores, (1011, 989))
        self.assertEqual(seen[2].scores, (1011, 989))
        self.assertEqual(seen[3].scores, (995, 1005))
        self.assertEqual(seen[-1].hands_remaining, 1)

    def test_unknown_hand_stops_match_without_mutating_ledger(self):
        calls = []

        def hand_runner(context):
            calls.append(context.hand_index)
            if context.hand_index == 2:
                return MatchHandResult.unknown(
                    "KONG_FEE_SETTLEMENT_UNKNOWN")
            reward = (10, -10) if context.dealer == 0 else (-10, 10)
            return MatchHandResult.settled(reward, winner=context.dealer)

        result = MatchRunner(hand_runner).run(initial_dealer=0)
        self.assertFalse(result.complete)
        self.assertEqual(result.status, "STOPPED_UNKNOWN")
        self.assertEqual(result.stopped_hand_index, 2)
        self.assertEqual(result.unresolved, ("KONG_FEE_SETTLEMENT_UNKNOWN",))
        self.assertEqual(result.progress.hand_index, 2)
        self.assertEqual(result.final_scores, (1020, 980))
        self.assertEqual(calls, [0, 1, 2])
        self.assertIsNone(result.hands[-1].scores_after)

    def test_unknown_rule_exception_is_converted_to_safe_stop(self):
        def hand_runner(context):
            raise UnknownRuleError("multi_gold_fan")

        result = MatchRunner(hand_runner).run()
        self.assertEqual(result.status, "STOPPED_UNKNOWN")
        self.assertEqual(result.unresolved, ("multi_gold_fan",))
        self.assertEqual(result.progress.hand_index, 0)
        self.assertEqual(result.final_scores, (1000, 1000))

    def test_runner_rejects_invalid_hand_result(self):
        with self.assertRaises(TypeError):
            MatchRunner(lambda context: (1, -1)).run()
        with self.assertRaises(ValueError):
            MatchHandResult.settled((1, 0), winner=0)
        with self.assertRaises(ValueError):
            MatchHandResult.unknown()


if __name__ == "__main__":
    unittest.main()
