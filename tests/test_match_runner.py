import unittest

from huian import UnknownRuleError
from workspace.simulator import (
    MatchHandResult, MatchRunner, SimulationResult, run_eight_hand_match,
    run_real_ordinary_match, summarize_match_rule_gaps,
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
                    "GANG_HU_SCORING_UNKNOWN")
            reward = (10, -10) if context.dealer == 0 else (-10, 10)
            return MatchHandResult.settled(reward, winner=context.dealer)

        result = MatchRunner(hand_runner).run(initial_dealer=0)
        self.assertFalse(result.complete)
        self.assertEqual(result.status, "STOPPED_UNKNOWN")
        self.assertEqual(result.stopped_hand_index, 2)
        self.assertEqual(result.unresolved, ("GANG_HU_SCORING_UNKNOWN",))
        self.assertEqual(result.progress.hand_index, 2)
        self.assertEqual(result.final_scores, (1020, 980))
        self.assertEqual(calls, [0, 1, 2])
        self.assertIsNone(result.hands[-1].scores_after)

    def test_unknown_rule_exception_is_converted_to_safe_stop(self):
        def hand_runner(context):
            raise UnknownRuleError("GANG_HU_SCORING_UNKNOWN")

        result = MatchRunner(hand_runner).run()
        self.assertEqual(result.status, "STOPPED_UNKNOWN")
        self.assertEqual(result.unresolved, ("GANG_HU_SCORING_UNKNOWN",))
        self.assertEqual(result.progress.hand_index, 0)
        self.assertEqual(result.final_scores, (1000, 1000))

    def test_real_ordinary_match_feeds_dealer_base_into_each_hand(self):
        calls = []

        class FakeSimulator:
            def run_normal_hand(self, **kwargs):
                calls.append(kwargs)
                dealer = kwargs["dealer"]
                base = kwargs["current_dealer_base"]
                rewards = (base, -base) if dealer == 0 else (-base, base)
                return SimulationResult(
                    seed=kwargs["seed"], status="COMPLETED",
                    rewards=rewards, winner=dealer, win_source="discard",
                    terminal_reason="AUTO_PINGHU",
                    simulation_only=True, real_scoring=True,
                )

        result = run_real_ordinary_match(
            seed=7,
            simulator=FakeSimulator(),
            agent_factories=(lambda seed: object(), lambda seed: object()),
            initial_dealer=0,
        )
        self.assertTrue(result.complete)
        self.assertEqual(result.final_scores, (1180, 820))
        self.assertEqual(
            [call["current_dealer_base"] for call in calls],
            [5, 10, 15, 20, 25, 30, 35, 40],
        )
        self.assertTrue(all(call["dealer"] == 0 for call in calls))
        self.assertEqual([call["seed"] for call in calls],
                         [7000 + i for i in range(8)])

    def test_real_ordinary_match_stops_on_rule_unknown(self):
        calls = []

        class FakeSimulator:
            def run_normal_hand(self, **kwargs):
                calls.append(kwargs)
                if len(calls) == 3:
                    return SimulationResult(
                        seed=kwargs["seed"], status="STOPPED_UNKNOWN",
                        unresolved=("GANG_HU_SCORING_UNKNOWN",),
                        simulation_only=True, real_scoring=True,
                        unknown_evidence={
                            "rule_ids": ["GANG_HU_SCORING_UNKNOWN"],
                            "phase": "HU_DECLARED",
                            "completed_kongs": [{"player": 0, "kind": "AN_GANG"}],
                        },
                    )
                return SimulationResult(
                    seed=kwargs["seed"], status="COMPLETED",
                    rewards=(5, -5), winner=0, win_source="discard",
                    terminal_reason="AUTO_PINGHU",
                    simulation_only=True, real_scoring=True,
                )

        result = run_real_ordinary_match(
            seed=1,
            simulator=FakeSimulator(),
            agent_factories=(lambda seed: object(), lambda seed: object()),
        )
        self.assertEqual(result.status, "STOPPED_UNKNOWN")
        self.assertEqual(result.stopped_hand_index, 2)
        self.assertEqual(result.unresolved, ("GANG_HU_SCORING_UNKNOWN",))
        self.assertEqual(result.final_scores, (1010, 990))
        self.assertEqual(len(calls), 3)
        self.assertEqual(
            result.stopped_evidence["phase"], "HU_DECLARED")
        self.assertEqual(
            result.hands[-1].result.evidence["completed_kongs"][0]["kind"],
            "AN_GANG")
        self.assertEqual(result.stopped_evidence["match_context"], {
            "hand_index": 2,
            "dealer": 0,
            "current_dealer_base": 15,
            "scores": [1010, 990],
            "hands_remaining": 6,
            "hand_seed": 1002,
        })

    def test_rule_gap_summary_counts_and_keeps_bounded_examples(self):
        def stopped(rule_id, marker):
            return MatchRunner(lambda context: MatchHandResult.unknown(
                rule_id, evidence={"marker": marker}
            )).run()

        complete = run_eight_hand_match(
            lambda context: MatchHandResult.settled(
                (0, 0), winner=None, terminal_reason="WALL_16"
            )
        )
        report = summarize_match_rule_gaps([
            stopped("GANG_HU_SCORING_UNKNOWN", "a"),
            stopped("decomposition_scoring", "b"),
            stopped("GANG_HU_SCORING_UNKNOWN", "c"),
            complete,
        ], max_examples_per_rule=1)

        self.assertEqual(report["total_matches"], 4)
        self.assertEqual(report["complete_matches"], 1)
        self.assertEqual(report["stopped_unknown"], 3)
        self.assertEqual(report["settled_hands_total"], 8)
        self.assertEqual(report["average_settled_hands"], 2.0)
        self.assertEqual(
            list(report["rules"]),
            ["GANG_HU_SCORING_UNKNOWN", "decomposition_scoring"],
        )
        self.assertEqual(
            report["rules"]["GANG_HU_SCORING_UNKNOWN"]["count"], 2)
        self.assertEqual(
            report["rules"]["GANG_HU_SCORING_UNKNOWN"]["examples"],
            [{"marker": "a"}],
        )
        with self.assertRaises(ValueError):
            summarize_match_rule_gaps([], max_examples_per_rule=-1)

    def test_runner_rejects_invalid_hand_result(self):
        with self.assertRaises(TypeError):
            MatchRunner(lambda context: (1, -1)).run()
        with self.assertRaises(ValueError):
            MatchHandResult.settled((1, 0), winner=0)
        with self.assertRaises(ValueError):
            MatchHandResult.unknown()


if __name__ == "__main__":
    unittest.main()
