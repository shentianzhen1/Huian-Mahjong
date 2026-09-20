import unittest
from types import SimpleNamespace
from unittest.mock import patch

from workspace.ai import MeldAwareShantenAgent, PublicRolloutAgent
from workspace.simulator.rollout_benchmark import (
    run_rollout_pilot, v010_factory, v014_factory,
)


class RolloutBenchmarkTests(unittest.TestCase):
    def test_factories_keep_versions_explicit(self):
        self.assertIsInstance(v010_factory(seed=1), MeldAwareShantenAgent)
        candidate = v014_factory(seed=1)
        self.assertIsInstance(candidate, PublicRolloutAgent)
        self.assertEqual(candidate.rollout_samples, 24)
        self.assertEqual(candidate.own_draws, 2)
        self.assertEqual(candidate.candidate_limit, 4)

    def test_pilot_uses_fresh_contiguous_seed_range_and_paired_runner(self):
        fake = SimpleNamespace(to_dict=lambda: {"ok": True})
        with patch(
                "workspace.simulator.rollout_benchmark.run_paired_real_matches",
                return_value=fake) as runner:
            result = run_rollout_pilot(pairs=3, seed_start=400000, max_steps=777)
        self.assertIs(result, fake)
        args, kwargs = runner.call_args
        self.assertEqual(tuple(args[0]), (400000, 400001, 400002))
        self.assertEqual(
            kwargs["agent_names"],
            ("PublicRolloutAgent V0.14 candidate",
             "MeldAwareShantenAgent V0.10"),
        )
        self.assertEqual(kwargs["max_steps"], 777)

    def test_invalid_pilot_inputs_rejected(self):
        with self.assertRaises(ValueError):
            run_rollout_pilot(pairs=0)
        with self.assertRaises(ValueError):
            run_rollout_pilot(pairs=True)
        with self.assertRaises(ValueError):
            run_rollout_pilot(seed_start=True)


if __name__ == "__main__":
    unittest.main()
