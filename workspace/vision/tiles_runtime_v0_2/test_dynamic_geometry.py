from __future__ import annotations

import unittest

from PIL import Image, ImageDraw

from .dynamic_geometry import detect_dynamic_geometry, fuse_dynamic_geometry


def synthetic_frame(draw_present: bool = False) -> Image.Image:
    image = Image.new("RGB", (1000, 480), (0, 55, 55))
    draw = ImageDraw.Draw(image)
    draw.rectangle((100, 400, 140, 470), fill=(230, 200, 50))
    for index in range(16):
        x = 180 + index * 45
        draw.rectangle((x, 400, x + 40, 470), fill="white")
    if draw_present:
        draw.rectangle((920, 400, 960, 470), fill="white")
    return image


class DynamicGeometryTests(unittest.TestCase):
    def test_detects_dynamic_sixteen_hand_slots_and_gold(self) -> None:
        result = detect_dynamic_geometry(synthetic_frame(), frame=1, session="s")
        self.assertFalse(result.geometry_untrusted)
        self.assertEqual(sum(item.region_candidate == "hand" for item in result.components), 16)
        self.assertEqual(sum(item.region_candidate == "gold" for item in result.components), 1)
        self.assertTrue(all(len(item.normalized_bbox) == 4 for item in result.components))

    def test_keeps_separated_draw_out_of_hand(self) -> None:
        result = detect_dynamic_geometry(synthetic_frame(draw_present=True))
        self.assertEqual(sum(item.region_candidate == "hand" for item in result.components), 16)
        self.assertEqual(sum(item.region_candidate == "draw" for item in result.components), 1)

    def test_requires_three_matching_trusted_frames(self) -> None:
        frames = [detect_dynamic_geometry(synthetic_frame(), frame=index) for index in range(3)]
        fused = fuse_dynamic_geometry(frames)
        self.assertFalse(fused.geometry_untrusted)
        self.assertIn("stable_votes=3", fused.issues)
        unstable = fuse_dynamic_geometry(frames[:2])
        self.assertTrue(unstable.geometry_untrusted)

    def test_gold_unknown_does_not_merge_into_hand_or_reject_stable_geometry(self) -> None:
        image = synthetic_frame()
        draw = ImageDraw.Draw(image)
        draw.rectangle((100, 400, 140, 470), fill=(0, 55, 55))
        result = detect_dynamic_geometry(image)
        self.assertFalse(result.geometry_untrusted)
        self.assertIn("gold_unreadable", result.issues)
        self.assertEqual(sum(item.region_candidate == "hand" for item in result.components), 16)


if __name__ == "__main__":
    unittest.main()
