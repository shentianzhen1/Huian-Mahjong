from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

VISION = all(
    importlib.util.find_spec(name) is not None
    for name in ("PIL", "cv2", "numpy")
)
REPO = Path(__file__).resolve().parents[1]


@unittest.skipUnless(VISION, "Pillow/OpenCV/numpy are optional in core-only installs")
class PublicMeldFeatureExperimentTests(unittest.TestCase):
    def test_real_query_experiment_is_source_disjoint_and_read_only(self):
        from workspace.vision.public_meld_feature_experiment import (
            FEATURES,
            evaluate_public_meld_features,
        )

        report = evaluate_public_meld_features(REPO)

        self.assertEqual(report["schema_version"], "public_meld_feature_experiment_v0_1")
        self.assertEqual(tuple(report["feature_variants"]), FEATURES)
        self.assertEqual(report["template_public_meld_label_count"], 21)
        self.assertTrue(report["query_match_group_excluded"])
        self.assertEqual(report["minimum_other_match_groups_per_class"], 2)
        self.assertFalse(report["changes_runtime_behavior"])
        self.assertFalse(report["formal_promotion_evidence"])
        self.assertFalse(report["safe_for_hint"])
        self.assertFalse(report["safe_for_executor"])

        for feature_name in FEATURES:
            row = report["results"][feature_name]
            self.assertEqual(row["query_count"], 2)
            self.assertGreaterEqual(row["top1_correct_count"], 0)
            self.assertLessEqual(row["top1_correct_count"], 2)
            self.assertEqual(len(row["queries"]), 2)
            for query in row["queries"]:
                self.assertEqual(query["eligible_class_count"], 2)
                self.assertIn(query["expected_tile"], {"P6", "S4"})

    def test_feature_extractors_reject_unknown_name(self):
        from PIL import Image
        from workspace.vision.public_meld_feature_experiment import (
            extract_public_meld_feature,
        )

        image = Image.new("RGB", (60, 80), "white")
        with self.assertRaisesRegex(ValueError, "unknown public meld feature"):
            extract_public_meld_feature(image, "not-a-feature")


if __name__ == "__main__":
    unittest.main()
