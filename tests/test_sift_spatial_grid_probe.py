import importlib.util
import unittest


@unittest.skipUnless(all(importlib.util.find_spec(name) for name in ("cv2", "numpy", "PIL")), "optional vision dependencies")
class SpatialGridDiagnosticTests(unittest.TestCase):
    def test_wrong_cell_cannot_reenter_via_raw_fallback(self):
        import numpy as np
        from workspace.vision.evaluate_sift_spatial_grid_probe import spatial_similarity
        a = np.zeros((3, 130), dtype="float32")
        b = a.copy()
        b[:, 128:] = 2
        self.assertIsNone(spatial_similarity(a, b))

    def test_mixing_frozen_and_grid_descriptors_is_rejected(self):
        import numpy as np
        from workspace.vision.evaluate_sift_spatial_grid_probe import spatial_similarity
        with self.assertRaisesRegex(ValueError, "descriptor\\+cell"):
            spatial_similarity(np.zeros((3, 128), dtype="float32"), np.zeros((3, 130), dtype="float32"))

    def test_blank_query_has_no_features(self):
        from PIL import Image
        from workspace.vision.evaluate_sift_spatial_grid_probe import spatial_descriptors
        self.assertIsNone(spatial_descriptors(Image.new("RGB", (45, 62), "white")))


if __name__ == "__main__":
    unittest.main()
