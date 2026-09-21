from __future__ import annotations

import unittest

from .tile_crop import classification_crop_bbox


class ClassificationCropTests(unittest.TestCase):
    def test_expands_vertical_tile_face(self) -> None:
        self.assertEqual(
            classification_crop_bbox([100, 80, 50, 70], frame_size=(300, 200)),
            (96, 70, 58, 84),
        )

    def test_horizontal_padding_stops_at_neighbor_midpoint(self) -> None:
        result = classification_crop_bbox(
            [100, 80, 50, 70],
            frame_size=(300, 200),
            neighbors=[[45, 80, 53, 70], [152, 80, 50, 70]],
        )
        self.assertEqual(result, (99, 70, 52, 84))

    def test_crop_stays_inside_frame(self) -> None:
        self.assertEqual(
            classification_crop_bbox([0, 2, 50, 70], frame_size=(52, 73)),
            (0, 0, 52, 73),
        )


if __name__ == "__main__":
    unittest.main()
