from __future__ import annotations

import importlib.util
import unittest

VISION = importlib.util.find_spec("PIL") is not None


@unittest.skipUnless(VISION, "Pillow is optional in core-only installs")
class PublicMeldIdentityNormalizationTests(unittest.TestCase):
    def setUp(self):
        from PIL import Image, ImageDraw

        self.Image = Image
        self.ImageDraw = ImageDraw

    def _face(self):
        image = self.Image.new("RGB", (100, 160), (238, 238, 230))
        draw = self.ImageDraw.Draw(image)
        draw.rectangle((0, 0, 99, 159), outline=(80, 80, 80), width=5)
        draw.ellipse((30, 50, 70, 90), fill=(20, 120, 50))
        return image

    def test_development_inset_preserves_output_size_and_is_not_runtime_safe(self):
        from workspace.vision.public_meld_identity_normalization import (
            DEVELOPMENT_IDENTITY_INSET_RATIO,
            normalize_public_meld_identity_query_face,
        )

        result = normalize_public_meld_identity_query_face(self._face())
        self.assertEqual(result.inset_ratio, DEVELOPMENT_IDENTITY_INSET_RATIO)
        self.assertEqual(result.input_size, (100, 160))
        self.assertEqual(result.output_size, (100, 160))
        self.assertEqual(result.image.size, (100, 160))

        report = result.to_dict()
        self.assertTrue(report["development_only"])
        self.assertTrue(report["selected_on_reviewed_queries"])
        self.assertEqual(report["intended_scope"], "query_side_split_face_only")
        self.assertFalse(report["template_bank_preprocessing_allowed"])
        self.assertFalse(report["formal_promotion_evidence"])
        self.assertFalse(report["safe_for_runtime"])
        self.assertFalse(report["safe_for_hint"])
        self.assertFalse(report["safe_for_executor"])

    def test_zero_inset_is_identity_transform_copy(self):
        from workspace.vision.public_meld_identity_normalization import (
            normalize_public_meld_identity_query_face,
        )

        source = self._face()
        result = normalize_public_meld_identity_query_face(source, inset_ratio=0.0)
        self.assertEqual(result.image.size, source.size)
        self.assertEqual(result.image.tobytes(), source.convert("RGB").tobytes())
        self.assertIn("query_identity_face_inset_disabled", result.issues)

    def test_invalid_insets_and_tiny_faces_fail_closed(self):
        from workspace.vision.public_meld_identity_normalization import (
            normalize_public_meld_identity_query_face,
        )

        for value in (-0.01, 0.5, 1.0, True, "0.12"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_public_meld_identity_query_face(
                        self._face(),
                        inset_ratio=value,
                    )

        tiny = self.Image.new("RGB", (7, 11), "white")
        with self.assertRaisesRegex(ValueError, "too small"):
            normalize_public_meld_identity_query_face(tiny)


if __name__ == "__main__":
    unittest.main()
