from __future__ import annotations

import unittest

from PIL import Image, ImageDraw

from .layout_stability import detect_bottom_layout


class LayoutStabilityTests(unittest.TestCase):
    def test_detects_bright_tiles_and_separated_draw(self) -> None:
        image = Image.new("RGB", (1000, 480), (0, 55, 55))
        draw = ImageDraw.Draw(image)
        for x in (200, 246, 292):
            draw.rectangle((x, 400, x + 40, 470), fill="white")
        draw.rectangle((500, 400, 540, 470), fill="white")
        draw.rectangle((100, 400, 140, 470), fill=(230, 200, 50))
        layout = detect_bottom_layout(image)
        self.assertEqual(len(layout.components), 4)
        self.assertIsNotNone(layout.possible_draw)
        self.assertIsNotNone(layout.gold_component)
        self.assertEqual(layout.hand_component_count, 3)

    def test_does_not_invent_a_draw_from_contiguous_tiles(self) -> None:
        image = Image.new("RGB", (1000, 480), (0, 55, 55))
        draw = ImageDraw.Draw(image)
        for x in (200, 246, 292, 338):
            draw.rectangle((x, 400, x + 40, 470), fill="white")
        layout = detect_bottom_layout(image)
        self.assertEqual(len(layout.components), 4)
        self.assertIsNone(layout.possible_draw)
        self.assertEqual(layout.hand_component_count, 4)


if __name__ == "__main__":
    unittest.main()
