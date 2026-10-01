import importlib.util
import unittest


VISION = all(
    importlib.util.find_spec(name) is not None
    for name in ("cv2", "numpy")
)


@unittest.skipUnless(VISION, "OpenCV/numpy are optional in core-only installs")
class PublicMeldHogSvmTests(unittest.TestCase):
    def test_fixed_ovr_svm_separates_simple_classes(self):
        import cv2
        import numpy as np

        if not hasattr(cv2, "ml") or not hasattr(cv2.ml, "SVM_create"):
            self.skipTest("OpenCV ml.SVM is unavailable")

        from workspace.vision.public_meld_hog_svm import (
            _fit_ovr_models,
            _svm_scores,
        )

        features = np.asarray(
            [
                [1.0, 0.0],
                [0.9, 0.1],
                [0.8, 0.05],
                [0.0, 1.0],
                [0.1, 0.9],
                [0.05, 0.8],
            ],
            dtype=np.float32,
        )
        labels = ["P1", "P1", "P1", "P2", "P2", "P2"]
        models = _fit_ovr_models(features, labels)
        self.assertEqual(set(models), {"P1", "P2"})

        first = _svm_scores(np.asarray([1.0, 0.0], dtype=np.float32), models)
        second = _svm_scores(np.asarray([0.0, 1.0], dtype=np.float32), models)
        self.assertGreater(first["P1"], first["P2"])
        self.assertGreater(second["P2"], second["P1"])

    def test_configuration_is_fixed_without_search(self):
        from workspace.vision.public_meld_hog_svm import (
            NEGATIVE_TO_POSITIVE_RATIO,
            SVM_C,
            SVM_MAX_ITERATIONS,
        )

        self.assertEqual(SVM_C, 1.0)
        self.assertEqual(NEGATIVE_TO_POSITIVE_RATIO, 3)
        self.assertEqual(SVM_MAX_ITERATIONS, 500)


if __name__ == "__main__":
    unittest.main()
