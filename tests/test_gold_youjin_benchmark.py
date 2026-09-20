import unittest
from types import SimpleNamespace
from unittest.mock import patch

from workspace.simulator.gold_youjin_benchmark import run_v015_ordinary_safety


class GoldYoujinBenchmarkTests(unittest.TestCase):
    def test_safety_pilot_uses_fresh_paired_seed_range_and_labels_scope(self):
        fake = SimpleNamespace(to_dict=lambda: {
            "completed_pairs": 2,
            "paired_score_delta_mean": 0.0,
        })
        with patch(
                "workspace.simulator.gold_youjin_benchmark.run_paired_real_matches",
                return_value=fake) as runner:
            result = run_v015_ordinary_safety(
                pairs=2, seed_start=420000, max_steps=777)

        args, kwargs = runner.call_args
        self.assertEqual(tuple(args[0]), (420000, 420001))
        self.assertEqual(kwargs["max_steps"], 777)
        self.assertEqual(
            kwargs["agent_names"],
            ("ConstrainedGoldYoujinAgent V0.15 candidate",
             "MeldAwareShantenAgent V0.10"),
        )
        self.assertIn("ordinary-safety-only", result["evaluation_scope"])
        self.assertIn("v015_diagnostics", result)

    def test_invalid_inputs_rejected(self):
        with self.assertRaises(ValueError):
            run_v015_ordinary_safety(pairs=0)
        with self.assertRaises(ValueError):
            run_v015_ordinary_safety(seed_start=True)


if __name__ == "__main__":
    unittest.main()
