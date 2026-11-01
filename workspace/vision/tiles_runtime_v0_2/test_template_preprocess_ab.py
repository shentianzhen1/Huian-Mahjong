from __future__ import annotations

import json
from pathlib import Path
import unittest

from PIL import Image

from workspace.vision.tiles_runtime_v0_2.template_preprocess_ab import (
    RUNTIME_THRESHOLD,
    build_ab_report,
    central7_feature,
)


ROOT = Path(__file__).resolve().parents[3]
DATASET = ROOT / "dataset" / "tiles_runtime_v0_2"


class TemplatePreprocessABTests(unittest.TestCase):
    def test_central7_feature_keeps_classifier_feature_shape(self):
        image = Image.new("RGB", (64, 96), "white")
        feature = central7_feature(image)
        self.assertEqual(feature.shape, (72, 48))

    def test_real_reviewed_dataset_ab_is_same_crop_and_frozen_threshold(self):
        report = build_ab_report(DATASET)
        self.assertEqual(report["threshold"], RUNTIME_THRESHOLD)
        self.assertEqual(RUNTIME_THRESHOLD, 0.82)
        self.assertTrue(report["development_only"])
        self.assertFalse(report["runtime_changed"])
        self.assertFalse(report["source_session_is_independent_match_evidence"])
        for mode in report["modes"].values():
            self.assertGreater(mode["same_query_count"], 0)
            self.assertEqual(
                mode["baseline"]["total"], mode["central7"]["total"]
            )
            self.assertEqual(mode["baseline"]["total"], mode["same_query_count"])
        # Intentionally emit the diagnostic so CI preserves the actual A/B
        # result without turning an exploratory accuracy difference into a
        # promotion gate.
        print("TEMPLATE_PREPROCESS_AB=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
