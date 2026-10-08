import unittest

import numpy as np
from PIL import Image, ImageDraw

from workspace.vision.concealed_template_match_lineage import ConcealedTemplateSource
from workspace.vision.tiles_runtime_v0_2.opened_gold_identity_probe import (
    summarize_match_disjoint_examples,
)
from workspace.vision.tiles_runtime_v0_2.opened_gold_scale_projection_probe import (
    _projected_gold_features,
)


class OpenedGoldScaleProjectionProbeTests(unittest.TestCase):
    @staticmethod
    def _tile_image():
        image = Image.new("RGB", (40, 64), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((10, 12, 29, 50), outline="black", width=3)
        draw.ellipse((15, 20, 25, 30), fill="black")
        return image

    def test_projection_variants_are_finite_and_fixed_feature_shape(self):
        features = _projected_gold_features(self._tile_image(), (90, 124))
        self.assertEqual(
            set(features),
            {
                "query_size_bicubic",
                "query_size_lanczos",
                "query_size_bicubic_blur_045",
            },
        )
        for feature in features.values():
            self.assertEqual(feature.shape, (72, 48))
            self.assertTrue(np.isfinite(feature).all())

    def test_invalid_target_face_size_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "too small"):
            _projected_gold_features(self._tile_image(), (4, 10))

    def test_synthetic_variants_do_not_create_independent_match_support(self):
        query_sha = "a" * 64
        same_match_sha = "b" * 64
        independent_sha = "c" * 64
        lineage = {
            query_sha: ConcealedTemplateSource(query_sha, "match-a", "evidence.json"),
            same_match_sha: ConcealedTemplateSource(
                same_match_sha, "match-a", "evidence.json"
            ),
            independent_sha: ConcealedTemplateSource(
                independent_sha, "match-b", "evidence.json"
            ),
        }
        rows = [
            {
                "tile_id": "P9",
                "source_sha256": same_match_sha,
                "projection_variant": "query_size_bicubic",
                "score": 0.95,
            },
            {
                "tile_id": "P9",
                "source_sha256": same_match_sha,
                "projection_variant": "query_size_lanczos",
                "score": 0.96,
            },
            {
                "tile_id": "P8",
                "source_sha256": independent_sha,
                "projection_variant": "query_size_bicubic",
                "score": 0.40,
            },
        ]
        result = summarize_match_disjoint_examples(
            rows,
            expected_tile="P9",
            source_sha=query_sha,
            query_match_group="match-a",
            lineage=lineage,
        )
        self.assertEqual(result["candidate_tile"], "P8")
        self.assertIsNone(result["expected_class_winner"])
        self.assertEqual(
            result["lineage_audit"]["excluded_same_original_match_count"], 2
        )
        self.assertTrue(result["original_match_disjointness_established"])
        self.assertFalse(result["formal_promotion_evidence"])


if __name__ == "__main__":
    unittest.main()
