"""Foreground-envelope checks independent of tile labels."""
import importlib.util
import unittest


@unittest.skipUnless(all(importlib.util.find_spec(n) for n in ('PIL', 'cv2', 'numpy')), 'optional vision dependencies')
class OuterBodyTests(unittest.TestCase):
    def image(self, dx=0, dy=0):
        from PIL import Image, ImageDraw
        image = Image.new('RGB', (250, 180), (3, 65, 76))
        draw = ImageDraw.Draw(image)
        draw.rectangle((45+dx, 55+dy, 174+dx, 119+dy), fill=(30, 110, 80))
        draw.rectangle((45+dx, 55+dy, 174+dx, 109+dy), fill=(225, 230, 220))
        return image

    def test_retains_dark_base_and_is_translation_equivariant(self):
        from workspace.vision.public_meld_outer_body_probe import outer_body_box
        box, _ = outer_body_box(self.image(), (40, 45, 140, 80))
        moved, _ = outer_body_box(self.image(9, 7), (49, 52, 140, 80))
        self.assertEqual(box, (45, 55, 175, 120))
        self.assertEqual(moved, (54, 62, 184, 127))

    def test_absent_foreground_abstains(self):
        from PIL import Image
        from workspace.vision.public_meld_outer_body_probe import outer_body_box
        box, audit = outer_body_box(Image.new('RGB', (250, 180), (3, 65, 76)), (40, 45, 140, 80))
        self.assertIsNone(box)
        self.assertEqual(audit['reason'], 'ambiguous_or_absent_body')

    def test_search_clipping_abstains(self):
        from PIL import ImageDraw
        from workspace.vision.public_meld_outer_body_probe import outer_body_box
        image = self.image()
        ImageDraw.Draw(image).rectangle((45, 55, 210, 119), fill=(225, 230, 220))
        box, audit = outer_body_box(image, (40, 45, 140, 80))
        self.assertIsNone(box)
        self.assertEqual(audit['reason'], 'body_touches_search_boundary')
