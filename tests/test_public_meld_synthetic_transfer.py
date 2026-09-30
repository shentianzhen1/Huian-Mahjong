import unittest

from PIL import Image, ImageDraw

from workspace.vision.public_meld_synthetic_transfer import (
    SYNTHETIC_BLUR_SIGMAS,
    SYNTHETIC_CANONICAL_SIZE,
    SYNTHETIC_TILT_FRACTIONS,
    render_self_meld_variants,
)


class PublicMeldSyntheticTransferTests(unittest.TestCase):
    def test_render_self_meld_variants_is_small_and_deterministic(self):
        image = Image.new("RGB", (40, 69), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((2, 2, 37, 66), outline="gray", width=1)
        draw.ellipse((12, 20, 28, 36), fill="red")
        draw.ellipse((12, 40, 28, 56), fill="blue")

        variants = render_self_meld_variants(image)

        self.assertEqual(
            len(variants),
            len(SYNTHETIC_TILT_FRACTIONS) * len(SYNTHETIC_BLUR_SIGMAS),
        )
        self.assertTrue(variants)
        self.assertTrue(
            all(variant.size == SYNTHETIC_CANONICAL_SIZE for variant in variants)
        )

    def test_first_batch_keeps_both_tilt_directions(self):
        self.assertLess(min(SYNTHETIC_TILT_FRACTIONS), 0)
        self.assertGreater(max(SYNTHETIC_TILT_FRACTIONS), 0)
        self.assertIn(0.0, SYNTHETIC_TILT_FRACTIONS)


if __name__ == "__main__":
    unittest.main()
