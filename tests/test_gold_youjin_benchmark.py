import unittest
from unittest.mock import patch
from types import SimpleNamespace

from workspace.ai import ConstrainedGoldYoujinAgent, MeldAwareShantenAgent
from workspace.simulator.gold_youjin_benchmark import (
    run_v015_pilot, v010_factory, v015_factory,
)


class GoldYoujinBenchmarkTests(unittest.TestCase):
    def test_factories_keep_versions_explicit(self):
        self.assertIsInstance(v010_factory(seed=1), MeldAwareShantenAgent)
        candidate = v015_factory(seed=1)
        self.assertIsInstance(candidate, ConstrainedGoldYoujinAgent)
        self.assertEqual(candidate.max_live_loss, 1)
        self.assertEqual(candidate.min_future_live_gain, 4)
        self.assertEqual(candidate.min_future_type_gain, 1)

    def test_pilot_uses_fresh_paired_seed_range(self):
        fake = SimpleNamespace(to_dict=lambda: {"ok": True})
        with patch(
                "workspace.simulator.gold_youjin_benchmark.run_paired_real_matches",
                return_value=fake) as runner:
            result = run_v015_pilot(pairs=2, seed_start=420000, max_steps=777)
        self.assertIs(result, fake)
        args, kwargs = runner.call_args
        self.assertEqual(tuple(args[0]), (420000, 420001))
        self.assertEqual(kwargs["max_steps"], 777)
        self.assertEqual(
            kwargs["agent_names"],
            ("ConstrainedGoldYoujinAgent V0.15 candidate",
             "MeldAwareShantenAgent V0.10"),
        )

    def test_invalid_inputs_rejected(self):
        with self.assertRaises(ValueError):
            run_v015_pilot(pairs=0)
        with self.assertRaises(ValueError):
            run_v015_pilot(seed_start=True)


if __name__ == "__main__":
    unittest.main()
