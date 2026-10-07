from __future__ import annotations

import unittest

import numpy as np
from PIL import Image

from workspace.vision.tiles_runtime_v0_2.concealed_shadow_appearance_probe import (
    DEVELOPMENT_SHADOW_DELTA_THRESHOLD,
    bottom_shadow_delta,
    shadow_appearance_candidate,
    shadow_template_normalize,
)


def _synthetic_tile(*, bottom_value: int) -> Image.Image:
    array = np.full((100, 70, 3), 225, dtype=np.uint8)
    # Simple dark glyph that does not touch the side-background measurement.
    array[20:75, 28:42] = 50
    array[82:, :, :] = bottom_value
    return Image.fromarray(array, mode="RGB")


class ConcealedShadowAppearanceProbeTests(unittest.TestCase):
    def test_ordinary_background_is_not_flagged(self):
        image = _synthetic_tile(bottom_value=220)
        delta = bottom_shadow_delta(image)
        self.assertGreater(delta, DEVELOPMENT_SHADOW_DELTA_THRESHOLD)
        self.assertFalse(shadow_appearance_candidate(image))

    def test_strong_bottom_shadow_is_flagged(self):
        image = _synthetic_tile(bottom_value=125)
        delta = bottom_shadow_delta(image)
        self.assertLessEqual(delta, DEVELOPMENT_SHADOW_DELTA_THRESHOLD)
        self.assertTrue(shadow_appearance_candidate(image))

    def test_shadow_template_candidate_removes_bottom_band_geometry(self):
        image = _synthetic_tile(bottom_value=125)
        normalized = shadow_template_normalize(image)
        self.assertLess(normalized.height, image.height)
        self.assertGreaterEqual(normalized.height, 12)


if __name__ == "__main__":
    unittest.main()
