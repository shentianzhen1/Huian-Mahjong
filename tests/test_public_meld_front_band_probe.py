import unittest
import importlib.util
from workspace.vision.public_meld_front_band_probe import front_band_bbox

VISION = all(importlib.util.find_spec(name) is not None for name in ("PIL", "cv2", "numpy"))
if VISION:
    from PIL import Image, ImageDraw

@unittest.skipUnless(VISION, "optional Vision dependencies")
class FrontBandProbeTests(unittest.TestCase):
    def test_darker_lower_side_is_removed_without_cutting_upper_glyph(self):
        image = Image.new("RGB", (60, 90), (180, 180, 180))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 59, 54), fill=(245, 245, 245))
        draw.rectangle((17, 6, 38, 15), fill=(10, 10, 10))
        draw.rectangle((18, 30, 40, 47), fill=(160, 0, 0))
        box, audit = front_band_bbox(image)
        self.assertEqual(box, (0, 0, 60, 57))
        self.assertFalse(audit["full_face_plane_rectification"])
        self.assertEqual(image.crop(box).getpixel((25, 47)), (160, 0, 0))

    def test_uniform_face_has_no_evidenced_side_boundary(self):
        box, audit = front_band_bbox(Image.new("RGB", (60, 90), (245, 245, 245)))
        self.assertIsNone(box)
        self.assertEqual(audit["reason"], "no_two_brightness_populations")

    def test_small_brightness_difference_abstains(self):
        image = Image.new("RGB", (60, 90), (235, 235, 235))
        ImageDraw.Draw(image).rectangle((0, 0, 59, 54), fill=(245, 245, 245))
        self.assertIsNone(front_band_bbox(image)[0])

    def test_dark_top_bright_bottom_is_not_a_lower_side_band(self):
        image = Image.new("RGB", (60, 90), (245, 245, 245))
        ImageDraw.Draw(image).rectangle((0, 0, 59, 25), fill=(180, 180, 180))
        self.assertIsNone(front_band_bbox(image)[0])

    def test_tiny_and_empty_crops_abstain_without_opencv_failure(self):
        for size in ((0, 0), (3, 4)):
            self.assertIsNone(front_band_bbox(Image.new("RGB", size))[0])

    def test_multiple_wide_bright_components_do_not_choose_a_cut(self):
        image = Image.new("RGB", (60, 90), (180, 180, 180))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 59, 54), fill=(245, 245, 245))
        draw.rectangle((0, 23, 59, 30), fill=(10, 10, 10))
        box, audit = front_band_bbox(image)
        self.assertIsNone(box)
        self.assertEqual(audit["reason"], "ambiguous_or_absent_front_component")


if __name__ == "__main__":
    unittest.main()
