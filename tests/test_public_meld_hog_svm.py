import importlib.util
import unittest


EXPERIMENT = all(
    importlib.util.find_spec(name) is not None
    for name in ("numpy", "sklearn")
)


@unittest.skipUnless(EXPERIMENT, "scikit-learn is experiment-only")
class PublicMeldHogSvmTests(unittest.TestCase):
    def test_fixed_linear_svc_separates_simple_classes(self):
        import numpy as np

        from workspace.vision.public_meld_hog_svm import (
            _fit_classifier,
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
        classifier = _fit_classifier(features, labels)

        first = _svm_scores(np.asarray([1.0, 0.0], dtype=np.float32), classifier)
        second = _svm_scores(np.asarray([0.0, 1.0], dtype=np.float32), classifier)
        self.assertGreater(first["P1"], first["P2"])
        self.assertGreater(second["P2"], second["P1"])

    def test_configuration_is_fixed_without_search(self):
        from workspace.vision.public_meld_hog_svm import (
            SVM_C,
            SVM_CLASS_WEIGHT,
            SVM_DUAL,
            SVM_MAX_ITERATIONS,
            SVM_RANDOM_STATE,
        )

        self.assertEqual(SVM_C, 1.0)
        self.assertEqual(SVM_CLASS_WEIGHT, "balanced")
        self.assertEqual(SVM_DUAL, "auto")
        self.assertEqual(SVM_MAX_ITERATIONS, 5000)
        self.assertEqual(SVM_RANDOM_STATE, 0)


if __name__ == "__main__":
    unittest.main()
