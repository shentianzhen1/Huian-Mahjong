import unittest

from workspace.vision.tiles_runtime_v0_2.opened_gold_normalization_ab import (
    NORMALIZATION_MODES,
    feature_for_mode,
    summarize_normalization_samples,
)


class OpenedGoldNormalizationABTests(unittest.TestCase):
    def test_runtime_mode_is_exact_production_gold_feature(self):
        import numpy as np
        from PIL import Image
        from workspace.vision.tiles_v0_1.template_classifier import _feature

        pixels = np.zeros((120, 88, 3), dtype=np.uint8)
        pixels[8:114, 6:82] = (220, 205, 95)
        pixels[24:98, 20:66] = (245, 245, 235)
        pixels[40:84, 32:56] = (40, 40, 40)
        image = Image.fromarray(pixels)
        self.assertTrue(np.array_equal(
            feature_for_mode(image, "runtime_gray"),
            _feature(image, region="gold_region"),
        ))

    def test_all_candidate_modes_are_fixed_shape_and_do_not_need_tile_id(self):
        import numpy as np
        from PIL import Image

        pixels = np.zeros((120, 88, 3), dtype=np.uint8)
        pixels[8:114, 6:82] = (230, 215, 100)
        pixels[26:100, 20:68] = (248, 248, 238)
        pixels[44:88, 30:58] = (20, 20, 20)
        image = Image.fromarray(pixels)
        for mode in NORMALIZATION_MODES:
            feature = feature_for_mode(image, mode)
            self.assertEqual(feature.shape, (72, 48))
            self.assertEqual(feature.dtype, np.uint8)
            self.assertTrue(np.isfinite(feature).all())

    def test_unknown_mode_fails_closed(self):
        from PIL import Image

        with self.assertRaisesRegex(ValueError, "unknown opened-Gold normalization mode"):
            feature_for_mode(Image.new("RGB", (32, 48), "white"), "secret_tuned_mode")

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
        summary = summarize_normalization_samples(samples, modes=("runtime_gray",))
        current = summary["current_bank"]["runtime_gray"]
        filtered = summary["exact_source_filtered"]["runtime_gray"]
        self.assertEqual(current["top1_correct"], 1)
        self.assertEqual(filtered["top1_correct"], 0)
        self.assertFalse(current["runtime_threshold_applied"])
        self.assertFalse(current["scores_are_runtime_acceptance"])
        self.assertFalse(current["formal_promotion_evidence"])


if __name__ == "__main__":
    unittest.main()
