"""Issue #69: shaded public meld appearance is NOT an acquired-tile fact."""
from __future__ import annotations

import importlib.util
import unittest

VISION = all(importlib.util.find_spec(x) is not None for x in ("PIL", "numpy"))


@unittest.skipUnless(VISION, "Vision dependencies are optional in core-only CI")
class PublicMeldIncomingShadeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PIL import Image, ImageDraw
        from workspace.vision.public_meld_incoming_shade import (
            detect_reviewed_meld_shade,
        )
        cls.Image = Image
        cls.ImageDraw = ImageDraw
        cls.detect = staticmethod(detect_reviewed_meld_shade)

    def tile(self, *, shade=False, glyph=0, value=195):
        image = self.Image.new("RGB", (44, 74), (value, value, value))
        pen = self.ImageDraw.Draw(image)
        # Distinctive high-contrast art must not itself count as an overlay.
        if glyph == 0:
            pen.ellipse((10, 21, 22, 33), fill=(35, 45, 48))
        elif glyph == 1:
            pen.rectangle((11, 21, 30, 30), fill=(15, 48, 52))
        else:
            pen.polygon([(8, 34), (26, 18), (35, 40)], fill=(35, 40, 39))
        if shade:
            image = image.point(lambda channel: round(channel * 0.70))
        return image

    def test_left_middle_right_synthetic_overlays_only_appearance(self):
        for position in (0, 1, 2):
            with self.subTest(shaded_slot=position):
                faces = [self.tile(glyph=i, shade=(i == position)) for i in range(3)]
                result = self.detect(faces, reviewed_meld_roi=True)
                self.assertEqual(result.shadow_index, position)
                self.assertGreaterEqual(result.darkness_gap, 28)
                self.assertLessEqual(result.brightness_v65[position], 165)
                payload = result.to_dict()
                self.assertEqual(payload["shadow_index"], position)
                self.assertEqual(payload["incoming_tile_id"], "UNKNOWN")
                self.assertFalse(payload["shade_is_confirmed_incoming_tile"])
                self.assertTrue(payload["requires_independent_discard_corroboration"])
                self.assertEqual(payload["actor"], "UNKNOWN")
                self.assertEqual(payload["action_kind"], "UNKNOWN")
                self.assertFalse(payload["safe_for_runtime"])
                self.assertFalse(payload["safe_for_executor"])
                self.assertFalse(payload["formal_promotion_evidence"])

    def test_different_artwork_without_face_wide_overlay_abstains(self):
        faces = [self.tile(glyph=i) for i in range(3)]
        result = self.detect(faces, reviewed_meld_roi=True)
        self.assertIsNone(result.shadow_index)
        self.assertEqual(result.reason, "ambiguous_or_no_unique_darkened_face")

    def test_same_global_dim_or_two_darkened_faces_abstain(self):
        for face_set in (
            [self.tile(shade=True) for _ in range(3)],
            [self.tile(shade=True), self.tile(shade=True), self.tile()],
            [self.tile(value=140), self.tile(value=180), self.tile(value=210)],
        ):
            with self.subTest(brightness=[x.getpixel((0, 0)) for x in face_set]):
                self.assertIsNone(
                    self.detect(face_set, reviewed_meld_roi=True).shadow_index
                )

    def test_gold_and_concealed_hand_lookalike_is_not_reviewed_meld(self):
        fake_gold_plus_hand = [
            self.tile(shade=True), self.tile(), self.tile()
        ]
        result = self.detect(fake_gold_plus_hand, reviewed_meld_roi=False)
        self.assertIsNone(result.shadow_index)
        self.assertEqual(result.reason, "unreviewed_or_non_meld_region")

    def test_stacked_kong_four_tiles_and_invalid_geometry_abstain(self):
        triplet = [self.tile(shade=True), self.tile(), self.tile()]
        self.assertEqual(
            self.detect(
                triplet, reviewed_meld_roi=True, layout="stacked_3_plus_1"
            ).reason, "unsupported_meld_geometry"
        )
        self.assertEqual(
            self.detect(
                triplet + [self.tile()], reviewed_meld_roi=True
            ).reason, "unsupported_meld_geometry"
        )
        self.assertEqual(
            self.detect(triplet[:2], reviewed_meld_roi=True).reason,
            "unsupported_meld_geometry",
        )

    def test_bad_crop_abstains_without_exposing_identity(self):
        faces = [self.tile(shade=True), self.tile(), self.tile()]
        faces[0] = self.Image.new("RGB", (9, 74), "gray")
        result = self.detect(faces, reviewed_meld_roi=True)
        self.assertIsNone(result.shadow_index)
        self.assertEqual(result.brightness_v65, ())
        self.assertFalse(result.to_dict()["safe_for_executor"])

    def test_relative_scores_are_not_probabilities(self):
        faces = [self.tile(), self.tile(shade=True), self.tile()]
        result = self.detect(faces, reviewed_meld_roi=True)
        self.assertEqual(result.shadow_index, 1)
        self.assertEqual(result.shadow_score[0], 0.0)
        self.assertEqual(result.shadow_score[2], 0.0)
        self.assertGreater(result.shadow_score[1], 28)
        self.assertGreater(sum(result.shadow_score), 1.0)


if __name__ == "__main__":
    unittest.main()
