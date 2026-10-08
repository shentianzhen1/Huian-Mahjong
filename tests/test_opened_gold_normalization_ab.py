import unittest

from workspace.vision.tiles_runtime_v0_2.opened_gold_normalization_ab import (
    NORMALIZATION_MODES,
    feature_for_mode,
    summarize_normalization_samples,
)


class OpenedGoldNormalizationABContractTests(unittest.TestCase):
    def test_fixed_modes_preserve_runtime_baseline_name(self):
        self.assertEqual(
            NORMALIZATION_MODES,
            (
                "runtime_gray",
                "face_only_gray",
                "face_only_edges",
                "inner_08_gray",
                "inner_08_edges",
            ),
        )

    def test_unknown_mode_fails_closed_before_vision_dependencies(self):
        with self.assertRaisesRegex(
            ValueError, "unknown opened-Gold normalization mode"
        ):
            feature_for_mode(object(), "secret_tuned_mode")

    def test_summary_is_ranking_only_and_never_applies_runtime_threshold(self):
        samples = [{
            "status": "SCORED_DETECTOR_CROP",
            "normalizations": {
                "runtime_gray": {
                    "current_bank": {
                        "expected_tile": "P9",
                        "candidate_tile": "P9",
                        "expected_class_rank": 1,
                        "expected_class_winner": {"score": 0.21},
                    },
                    "exact_source_filtered": {
                        "expected_tile": "P9",
                        "candidate_tile": "P8",
                        "expected_class_rank": 2,
                        "expected_class_winner": {"score": 0.18},
                    },
                }
            },
        }]
        summary = summarize_normalization_samples(
            samples, modes=("runtime_gray",)
        )
        current = summary["current_bank"]["runtime_gray"]
        filtered = summary["exact_source_filtered"]["runtime_gray"]
        self.assertEqual(current["top1_correct"], 1)
        self.assertEqual(filtered["top1_correct"], 0)
        self.assertFalse(current["runtime_threshold_applied"])
        self.assertFalse(current["scores_are_runtime_acceptance"])
        self.assertFalse(current["formal_promotion_evidence"])


if __name__ == "__main__":
    unittest.main()
