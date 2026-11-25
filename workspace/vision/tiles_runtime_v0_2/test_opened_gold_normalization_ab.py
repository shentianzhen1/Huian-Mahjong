import unittest

from workspace.vision.tiles_runtime_v0_2.opened_gold_normalization_ab import (
    NORMALIZATION_MODES,
    feature_for_mode,
)


class OpenedGoldNormalizationABVisionTests(unittest.TestCase):
    def test_runtime_mode_is_exact_production_gold_feature(self):
        import numpy as np
        from PIL import Image
        from workspace.vision.tiles_v0_1.template_classifier import _feature

        pixels = np.zeros((120, 88, 3), dtype=np.uint8)
        pixels[8:114, 6:82] = (220, 205, 95)
        pixels[24:98, 20:66] = (245, 245, 235)
        pixels[40:84, 32:56] = (40, 40, 40)
        image = Image.fromarray(pixels)
        self.assertTrue(
            np.array_equal(
                feature_for_mode(image, "runtime_gray"),
                _feature(image, region="gold_region"),
            )
        )

    def test_all_candidate_modes_are_fixed_shape_and_do_not_need_tile_id(self):
        import numpy as np
        from PIL import Image

        pixels = np.zeros((120, 88, 3), dtype=np.uint8)
        pixels[8:114, 6:82] = (230, 215, 100)
        pixels[26:100, 20:68] = (248, 248, 238)
        pixels[44:88, 30:58] = (20, 20, 20)
        image = Image.fromarray(pixels)
        for mode in NORMALIZATION_MODES:
            feature = feature_for_mode(image, mode)
            self.assertEqual(feature.shape, (72, 48))
            self.assertEqual(feature.dtype, np.uint8)
            self.assertTrue(np.isfinite(feature).all())


if __name__ == "__main__":
    unittest.main()
