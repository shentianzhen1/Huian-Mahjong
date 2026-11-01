import unittest

try:
    import cv2  # noqa: F401
    import numpy as np
    from PIL import Image
except ImportError:
    cv2 = None
    np = None
    Image = None

from workspace.vision.public_meld_dark_face_probe import dark_face_front_band_bbox


@unittest.skipIf(cv2 is None or np is None or Image is None, "optional Vision dependencies")
class DarkFaceFrontBandProbeTests(unittest.TestCase):
    @staticmethod
    def _image():
        a = np.full((96, 80, 3), 105, dtype=np.uint8)
        a[4:76, :] = 150
        a[76:, :] = 92
        return Image.fromarray(a)

    def test_fallback_rejects_every_other_primary_reason(self):
        for reason in ("development_front_band_candidate", "no_lower_side_band",
                       "lower_band_not_darker", "weak_brightness_separation",
                       "normalization_abstained"):
            box, audit = dark_face_front_band_bbox(self._image(), {"reason": reason})
            self.assertIsNone(box)
            self.assertEqual(audit["reason"], "fallback_not_permitted")

    def test_fallback_remains_development_only_and_fail_closed(self):
        _, audit = dark_face_front_band_bbox(
            self._image(), {"reason": "ambiguous_or_absent_front_component"})
        self.assertTrue(audit["development_only"])
        self.assertFalse(audit["runtime_integration"])
        self.assertEqual(audit["tile_identity"], "UNKNOWN")
        self.assertFalse(audit["safe_for_runtime"])
        self.assertFalse(audit["safe_for_hint"])
        self.assertFalse(audit["safe_for_executor"])

    def test_uniform_crop_cannot_be_forced_through_fallback(self):
        image = Image.new("RGB", (80, 96), (100, 100, 100))
        box, audit = dark_face_front_band_bbox(
            image, {"reason": "ambiguous_or_absent_front_component"})
        self.assertIsNone(box)
        self.assertIn(audit["reason"], {
            "insufficient_body", "no_two_brightness_populations", "weak_brightness_separation",
            "ambiguous_or_absent_front_component", "no_lower_side_band",
            "lower_band_not_darker",
        })


if __name__ == "__main__":
    unittest.main()
