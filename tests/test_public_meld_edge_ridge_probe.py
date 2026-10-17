import importlib.util
import unittest
from workspace.vision.public_meld_edge_ridge_probe import prepare_edge_ridge_band

VISION = all(importlib.util.find_spec(name) is not None for name in ("PIL", "cv2", "numpy"))
if VISION:
    from PIL import Image, ImageDraw


@unittest.skipUnless(VISION, "optional Vision dependencies")
class EdgeRidgeTests(unittest.TestCase):
    def face(self):
        im = Image.new("RGB", (60, 90), (140, 140, 140))
        draw = ImageDraw.Draw(im)
        draw.rectangle((0, 55, 59, 58), fill=(160, 160, 160))
        draw.rectangle((0, 59, 59, 89), fill=(100, 100, 100))
        draw.rectangle((18, 10, 40, 45), fill=(0, 100, 0))
        return im

    def test_own_bevel_and_terminal_wall_support_surface(self):
        crop, audit = prepare_edge_ridge_band(self.face())
        self.assertIsNotNone(crop)
        self.assertEqual(audit["reason"], "own_pixel_ridge_candidate")
        self.assertFalse(audit["neighbor_plane_extrapolated"])
        self.assertFalse(audit["raw_feature_fallback"])
        self.assertFalse(audit["safe_for_runtime"])

    def test_uniform_face_or_19_value_rise_cannot_supply_ridge(self):
        im = self.face()
        ImageDraw.Draw(im).rectangle((0, 55, 59, 58), fill=(159, 159, 159))
        for candidate in (im, Image.new("RGB", (60, 90), (140, 140, 140))):
            self.assertIsNone(prepare_edge_ridge_band(candidate)[0])

    def test_narrow_ridge_cannot_use_an_isolated_bright_patch(self):
        im = self.face()
        draw = ImageDraw.Draw(im)
        draw.rectangle((0, 55, 59, 58), fill=(140, 140, 140))
        draw.rectangle((18, 55, 32, 58), fill=(160, 160, 160))
        self.assertIsNone(prepare_edge_ridge_band(im)[0])

    def test_highlight_with_equal_lower_surface_is_not_a_wall(self):
        im = self.face()
        ImageDraw.Draw(im).rectangle((0, 59, 59, 89), fill=(140, 140, 140))
        self.assertIsNone(prepare_edge_ridge_band(im)[0])

    def test_dark_glyph_stripe_followed_by_face_is_not_terminal_wall(self):
        im = self.face()
        ImageDraw.Draw(im).rectangle((0, 75, 59, 89), fill=(140, 140, 140))
        crop, audit = prepare_edge_ridge_band(im)
        self.assertIsNone(crop)
        self.assertEqual(audit["reason"], "darker_stripe_is_not_terminal_wall")

    def test_multiple_ridges_and_tiny_images_abstain(self):
        im = self.face()
        ImageDraw.Draw(im).rectangle((0, 20, 59, 22), fill=(160, 160, 160))
        for candidate in (im, Image.new("RGB", (3, 4), "white")):
            self.assertIsNone(prepare_edge_ridge_band(candidate)[0])


if __name__ == "__main__":
    unittest.main()
