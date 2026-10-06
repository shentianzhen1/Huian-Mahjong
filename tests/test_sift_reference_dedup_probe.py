"""Offline-only aggregation behavior, independent of private query pixels."""
import importlib.util
import unittest
from types import SimpleNamespace

from workspace.vision.evaluate_sift_reference_dedup_probe import unique_reference_distances


class UniqueReferenceDistancesTests(unittest.TestCase):
    def test_many_query_matches_do_not_inflate_reference_support(self):
        matches = [SimpleNamespace(trainIdx=1, distance=d) for d in (30, 20, 40)]
        matches.append(SimpleNamespace(trainIdx=2, distance=50))
        self.assertEqual(unique_reference_distances(matches), [20., 50.])
        self.assertEqual(unique_reference_distances(list(reversed(matches))), [20., 50.])

    def test_empty_matches_have_no_support(self):
        self.assertEqual(unique_reference_distances([]), [])

    @unittest.skipUnless(importlib.util.find_spec("cv2") and importlib.util.find_spec("numpy"), "optional vision dependencies")
    def test_missing_descriptors_abstain(self):
        from workspace.vision.evaluate_sift_reference_dedup_probe import unique_reference_similarity
        self.assertIsNone(unique_reference_similarity(None, None))

    @unittest.skipUnless(importlib.util.find_spec("cv2") and importlib.util.find_spec("numpy"), "optional vision dependencies")
    def test_ratio_and_raw_fallback_keep_only_best_distance_per_reference(self):
        from unittest.mock import patch
        import numpy as np
        from workspace.vision.evaluate_sift_reference_dedup_probe import match_audit

        matches = [SimpleNamespace(trainIdx=t, distance=d) for t, d in ((0, 10), (0, 20), (1, 30))]
        arrays = np.zeros((3, 128), dtype="float32")
        for fallback in (False, True):
            matcher = SimpleNamespace(
                knnMatch=lambda *args, **kwargs: [] if fallback else [(m, SimpleNamespace(distance=100)) for m in matches],
                match=lambda *args, **kwargs: matches,
            )
            with patch("cv2.BFMatcher", return_value=matcher):
                audit = match_audit(arrays, arrays)
            self.assertEqual(audit["raw_fallback_used"], fallback)
            self.assertEqual(audit["counted_matches_before"], 3)
            self.assertEqual(audit["unique_reference_descriptors"], 2)
            self.assertEqual(audit["maximum_query_matches_to_one_reference"], 2)
            self.assertAlmostEqual(audit["deduplicated_score"], 2 / 21)


if __name__ == "__main__":
    unittest.main()
