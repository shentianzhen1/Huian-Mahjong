from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

VISION = all(
    importlib.util.find_spec(name) is not None
    for name in ("PIL", "cv2", "numpy")
)

ROOT = Path(__file__).resolve().parents[1]
CALIBRATION = ROOT / "references/vision/2026-09-22/public_detector_calibration_v0_1.json"


@unittest.skipUnless(VISION, "Pillow/OpenCV/numpy are optional in core-only installs")
class PublicMeldGeometryNormalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PIL import Image, ImageDraw
        from workspace.vision.public_meld_geometry_normalization import (
            FLAT,
            STACKED,
            UNKNOWN,
            normalize_public_meld_crop,
            split_flat_meld_faces,
        )
        from workspace.vision.public_tile_detector import PublicGeometryCandidate

        cls.Image = Image
        cls.ImageDraw = ImageDraw
        cls.FLAT = FLAT
        cls.STACKED = STACKED
        cls.UNKNOWN = UNKNOWN
        cls.normalize = staticmethod(normalize_public_meld_crop)
        cls.split = staticmethod(split_flat_meld_faces)
        cls.PublicGeometryCandidate = PublicGeometryCandidate
        cls.calibration = json.loads(CALIBRATION.read_text(encoding="utf-8"))

    def _candidate(self, bbox, *, confidence=0.9, geometry_kind="bottom_group"):
        return self.PublicGeometryCandidate(
            pixel_bbox=bbox,
            normalized_bbox=(0.0, 0.0, 1.0, 1.0),
            geometry_kind=geometry_kind,
            confidence=confidence,
            fill_ratio=0.8,
            frame="synthetic",
            session="synthetic",
        )

    def _flat_image(self):
        image = self.Image.new("RGB", (240, 150), (0, 75, 78))
        draw = self.ImageDraw.Draw(image)
        for x in (25, 85, 145):
            draw.rectangle((x, 40, x + 54, 125), fill=(235, 235, 225))
        return image

    def _stacked_image(self):
        image = self.Image.new("RGB", (240, 170), (0, 75, 78))
        draw = self.ImageDraw.Draw(image)
        for x in (25, 85, 145):
            draw.rectangle((x, 70, x + 54, 155), fill=(235, 235, 225))
        draw.rectangle((85, 15, 139, 100), fill=(235, 235, 225))
        return image

    def test_flat_row_normalizes_and_splits_three_faces(self):
        image = self._flat_image()
        normalized = self.normalize(
            image,
            self._candidate((20, 30, 185, 105)),
        )
        self.assertEqual(normalized.analysis.stack_state, self.FLAT)
        self.assertEqual(normalized.analysis.normalized_size[1], 96)
        faces = self.split(normalized)
        self.assertEqual(len(faces), 3)
        self.assertTrue(all(face.size[1] == 96 for face in faces))
        self.assertTrue(all(face.size[0] > 0 for face in faces))

    def test_stacked_3_plus_1_is_detected_and_not_equal_thirds_split(self):
        image = self._stacked_image()
        normalized = self.normalize(
            image,
            self._candidate((20, 10, 185, 150)),
        )
        self.assertEqual(normalized.analysis.stack_state, self.STACKED)
        self.assertLess(normalized.analysis.top_to_mid_span_ratio, 0.68)
        self.assertEqual(self.split(normalized), ())
        self.assertIn(
            "stacked_3_plus_1_geometry_candidate",
            normalized.analysis.issues,
        )

    def test_moderate_height_stack_is_not_lost(self):
        image = self.Image.new("RGB", (300, 180), (0, 75, 78))
        draw = self.ImageDraw.Draw(image)
        for x in (20, 105, 190):
            draw.rectangle((x, 65, x + 74, 145), fill=(235, 235, 225))
        draw.rectangle((105, 15, 179, 95), fill=(235, 235, 225))
        normalized = self.normalize(
            image,
            self._candidate((15, 10, 255, 145)),
        )
        self.assertEqual(
            normalized.analysis.stack_state,
            self.STACKED,
            repr(normalized.analysis),
        )
        self.assertEqual(self.split(normalized), ())

    def test_upper_flat_row_uses_same_normalization_and_split(self):
        image = self._flat_image()
        normalized = self.normalize(
            image,
            self._candidate(
                (20, 30, 185, 105),
                geometry_kind="top_group",
            ),
        )
        self.assertEqual(normalized.analysis.stack_state, self.FLAT)
        self.assertEqual(normalized.analysis.normalized_size[1], 96)
        self.assertEqual(len(self.split(normalized)), 3)

    def test_non_bottom_group_remains_unknown(self):
        image = self._flat_image()
        group = self.PublicGeometryCandidate(
            pixel_bbox=(20, 30, 185, 105),
            normalized_bbox=(0.0, 0.0, 1.0, 1.0),
            geometry_kind="single_face",
            confidence=0.9,
            fill_ratio=0.8,
            frame="synthetic",
            session="synthetic",
        )
        normalized = self.normalize(image, group)
        self.assertEqual(normalized.analysis.stack_state, self.UNKNOWN)
        self.assertIsNone(normalized.image)
        self.assertEqual(normalized.analysis.issues, ("not_meld_group",))

    def _reviewed(self, sample_id):
        row = next(
            item for item in self.calibration["samples"]
            if item["sample_id"] == sample_id
        )
        image = self.Image.open(ROOT / row["image_path"]).convert("RGB")
        x, y, width, height = row["bbox"]
        px = (
            int(round(x * image.width)),
            int(round(y * image.height)),
            int(round(width * image.width)),
            int(round(height * image.height)),
        )
        return image, self._candidate(px)

    def test_reviewed_player_peng_is_flat(self):
        image, group = self._reviewed("66fe_player_peng_p1_040s")
        normalized = self.normalize(image, group)
        self.assertEqual(normalized.analysis.stack_state, self.FLAT)
        self.assertEqual(len(self.split(normalized)), 3)

    def test_reviewed_player_added_kong_is_stacked(self):
        image, group = self._reviewed("66fe_player_added_kong_p1_070s")
        normalized = self.normalize(image, group)
        self.assertEqual(
            normalized.analysis.stack_state,
            self.STACKED,
            repr(normalized.analysis),
        )
        self.assertEqual(self.split(normalized), ())

    def test_reviewed_player_chi_is_flat(self):
        image, group = self._reviewed("66fe_player_chi_s789_082s")
        normalized = self.normalize(image, group)
        self.assertEqual(
            normalized.analysis.stack_state,
            self.FLAT,
            repr(normalized.analysis),
        )
        self.assertEqual(len(self.split(normalized)), 3)


if __name__ == "__main__":
    unittest.main()
