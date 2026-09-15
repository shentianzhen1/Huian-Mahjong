import json
import unittest

from workspace.ai import BaselineAgent
from workspace.simulator import RandomAgent, Simulator, SimulationResult, run_many_normal_hands


class BatchEvaluationTests(unittest.TestCase):
    def test_random_vs_baseline_fixed_seed_seat_swap_reproduces(self):
        options = dict(agent_factories=(RandomAgent, BaselineAgent),
                       max_steps=1000, swap_seats=True)
        first = run_many_normal_hands((0, 3, 7), **options)
        second = Simulator().run_many_normal_hands((0, 3, 7), **options)
        self.assertEqual(first, second)
        self.assertEqual(first.total, 6)
        self.assertEqual(first.total, first.completed + first.unknown)
        self.assertEqual(first.max_steps, 0)
        self.assertEqual(first.stopped_loops, 0)
        self.assertEqual(first.completed, sum(first.wins) + first.draws)
        self.assertEqual(sum(first.wins), first.self_draws + first.discard_wins)
        self.assertEqual(sum(first.average_reward), 0)
        self.assertEqual(first.by_agent["A"]["name"], "RandomAgent")
        self.assertEqual(first.by_agent["B"]["name"], "BaselineAgent")
        self.assertEqual(first.by_agent["A"]["hands"], 6)
        for pair_start in range(0, 6, 2):
            a, b = first.per_seed[pair_start:pair_start + 2]
            self.assertEqual(a.seed, b.seed)
            self.assertEqual(a.wall_hash, b.wall_hash)
            self.assertEqual(a.initial_state_hash, b.initial_state_hash)
            self.assertEqual(a.agents, tuple(reversed(b.agents)))
            self.assertFalse(a.swapped)
            self.assertTrue(b.swapped)
        json.dumps(first.to_dict())

    def test_censored_hands_do_not_count_as_losses_draws_or_reward_samples(self):
        # Known accounting examples; actual game endings are tested with fixed walls.
        results = [
            SimulationResult(0, "COMPLETED", winner=0, win_source="discard",
                             terminal_reason="SIMULATION_PINGHU", rewards=(1, -1)),
            SimulationResult(1, "COMPLETED", winner=1, win_source="self_draw",
                             terminal_reason="SIMULATION_ZIMO", rewards=(-2, 2)),
            SimulationResult(2, "COMPLETED", terminal_reason="WALL_16"),
            SimulationResult(3, "STOPPED_UNKNOWN", unresolved=("rob_kong",)),
            SimulationResult(4, "MAX_STEPS", stop_reason="max_steps"),
            SimulationResult(5, "STOPPED_LOOP", stop_reason="repeated position"),
        ]

        class FixtureSimulator:
            def run_normal_hand(self, *, seed, **options):
                return results[seed]

        report = run_many_normal_hands(range(6), simulator=FixtureSimulator())
        self.assertEqual(report.wins, (1, 1))
        self.assertEqual(report.losses, (1, 1))
        self.assertEqual((report.completed, report.draws, report.self_draws, report.discard_wins),
                         (3, 1, 1, 1))
        self.assertEqual((report.unknown, report.max_steps, report.stopped_loops), (1, 1, 1))
        self.assertEqual(report.reward_samples, 3)
        self.assertEqual(report.average_reward, (-1 / 3, 1 / 3))
        self.assertEqual(report.unknown_reasons, {"rob_kong": 1})
        self.assertEqual(report.by_agent["A"]["reward_sum"], -1)
        self.assertEqual(report.by_agent["B"]["reward_sum"], 1)

    def test_all_censored_is_explicitly_zero_samples(self):
        result = run_many_normal_hands([1], max_steps=1)
        self.assertEqual(result.reward_samples, 0)
        self.assertEqual(result.average_reward, (0.0, 0.0))
        self.assertEqual(result.draws, 0)
        self.assertEqual(result.total, result.unknown + result.max_steps)

    def test_fresh_agent_rng_is_stable_when_seats_swap(self):
        calls = []

        def factory(seed):
            calls.append(seed)
            return RandomAgent(seed)

        run_many_normal_hands([5, 8], agent_factories=(factory, factory),
                              swap_seats=True, max_steps=1)
        self.assertEqual(calls, [10, 11, 10, 11, 16, 17, 16, 17])

    def test_invalid_batch_arguments_are_rejected(self):
        for seeds in ([], [True], ["1"]):
            with self.assertRaises(ValueError):
                run_many_normal_hands(seeds)
        with self.assertRaises(ValueError):
            run_many_normal_hands([1], agent_factories=(RandomAgent,))
        with self.assertRaises(ValueError):
            run_many_normal_hands([1], max_steps=0)


if __name__ == "__main__":
    unittest.main()
