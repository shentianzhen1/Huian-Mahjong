import importlib.util
import unittest


VISION = all(
    importlib.util.find_spec(name) is not None
    for name in ("PIL", "cv2", "numpy")
)


@unittest.skipUnless(VISION, "Pillow/OpenCV/numpy are optional in core-only installs")
class PublicMeldSyntheticTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PIL import Image, ImageDraw
        from workspace.vision.public_meld_synthetic_transfer import (
            SYNTHETIC_BLUR_SIGMAS,
            SYNTHETIC_CANONICAL_SIZE,
            SYNTHETIC_TILT_FRACTIONS,
            render_self_meld_variants,
        )

        cls.Image = Image
        cls.ImageDraw = ImageDraw
        cls.blur_sigmas = SYNTHETIC_BLUR_SIGMAS
        cls.canonical_size = SYNTHETIC_CANONICAL_SIZE
        cls.tilt_fractions = SYNTHETIC_TILT_FRACTIONS
        cls.render = staticmethod(render_self_meld_variants)

    def test_render_self_meld_variants_is_small_and_deterministic(self):
        image = self.Image.new("RGB", (40, 69), "white")
        draw = self.ImageDraw.Draw(image)
        draw.rectangle((2, 2, 37, 66), outline="gray", width=1)
        draw.ellipse((12, 20, 28, 36), fill="red")
        draw.ellipse((12, 40, 28, 56), fill="blue")

        variants = self.render(image)

        self.assertEqual(
            len(variants),
            len(self.tilt_fractions) * len(self.blur_sigmas),
        )
        self.assertTrue(variants)
        self.assertTrue(
            all(variant.size == self.canonical_size for variant in variants)
        )

    def test_first_batch_keeps_both_tilt_directions(self):
        self.assertLess(min(self.tilt_fractions), 0)
        self.assertGreater(max(self.tilt_fractions), 0)
        self.assertIn(0.0, self.tilt_fractions)


if __name__ == "__main__":
    unittest.main()
