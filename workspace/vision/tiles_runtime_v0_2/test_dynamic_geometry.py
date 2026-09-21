from __future__ import annotations

import unittest

from PIL import Image, ImageDraw

from .dynamic_geometry import (
    _recover_gap_meld_faces,
    _recover_stacked_meld_faces,
    detect_dynamic_geometry,
    fuse_dynamic_geometry,
)


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


def meld_and_draw_frame(offset: int = 0) -> Image.Image:
    image = Image.new("RGB", (1000, 480), (0, 55, 55))
    draw = ImageDraw.Draw(image)
    # A small, lower-height two-tile group is separated from the dominant
    # concealed run.  Its position changes with offset to guard against a
    # fixed-x shortcut.
    draw.rectangle((220 + offset, 410, 260 + offset, 460), fill="white")
    draw.rectangle((300 + offset, 410, 340 + offset, 460), fill="white")
    draw.rectangle((394 + offset, 400, 434 + offset, 470), fill=(230, 200, 50))
    for index in range(9):
        x = 440 + offset + index * 45
        draw.rectangle((x, 400, x + 40, 470), fill="white")
    draw.rectangle((880 + offset, 400, 920 + offset, 470), fill="white")
    return image


def joined_right_edge_frame() -> Image.Image:
    image = Image.new("RGB", (1000, 480), (0, 55, 55))
    draw = ImageDraw.Draw(image)
    draw.rectangle((100, 400, 140, 470), fill=(230, 200, 50))
    for index in range(10):
        x = 250 + index * 45
        draw.rectangle((x, 400, x + 40, 470), fill="white")
    # These two tiles touch and therefore enter connected-components as one
    # bright box.  No expected hand count is supplied to the detector.
    draw.rectangle((700, 400, 740, 470), fill="white")
    draw.rectangle((740, 400, 780, 470), fill="white")
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
        self.assertEqual(sum(item.region_candidate == "draw_visual" for item in result.components), 1)

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

    def test_separates_meld_from_hand_without_fixed_x_coordinates(self) -> None:
        for offset in (0, -100):
            result = detect_dynamic_geometry(meld_and_draw_frame(offset))
            self.assertFalse(result.geometry_untrusted)
            self.assertEqual(sum(item.region_candidate == "hand" for item in result.components), 9)
            self.assertEqual(sum(item.region_candidate == "meld" for item in result.components), 2)
            self.assertEqual(sum(item.region_candidate == "draw_visual" for item in result.components), 1)

    def test_splits_a_joined_right_edge_component_from_observed_width(self) -> None:
        result = detect_dynamic_geometry(joined_right_edge_frame())
        self.assertFalse(result.geometry_untrusted)
        self.assertEqual(sum(item.region_candidate == "hand" for item in result.components), 12)

    def test_recovers_overlapping_lower_face_from_stacked_meld_geometry(self) -> None:
        recovered = _recover_stacked_meld_faces(
            [(4, 588, 61, 81), (65, 588, 46, 81), (110, 603, 58, 66)],
            typical_width=59,
        )
        self.assertEqual(recovered, [(58, 603, 59, 66)])

    def test_recovers_dark_face_from_local_meld_gap(self) -> None:
        recovered = _recover_gap_meld_faces(
            [(4, 603, 61, 67), (109, 603, 59, 67)],
            typical_width=59,
        )
        self.assertEqual(recovered, [(63, 603, 48, 67)])


if __name__ == "__main__":
    unittest.main()
