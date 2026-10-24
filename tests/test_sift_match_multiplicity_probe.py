import importlib.util
import unittest


@unittest.skipUnless(all(importlib.util.find_spec(n) for n in ('cv2', 'numpy')), 'optional vision dependencies')
class MatchMultiplicityTests(unittest.TestCase):
    def test_duplicate_local_matches_are_not_independent_reference_points(self):
        import numpy as np
        from workspace.vision.sift_match_multiplicity_probe import match_multiplicity
        query = np.zeros((4,128), dtype=np.float32)
        reference = np.array([np.zeros(128), np.ones(128)*100], dtype=np.float32)
        audit = match_multiplicity(query, reference)
        self.assertEqual(audit['scoring_matches'], 4)
        self.assertEqual(audit['unique_reference_descriptor_indices'], 1)
        self.assertEqual(audit['many_to_one_reuse_count'], 3)
        self.assertFalse(audit['spatial_consistency_checked'])

    def test_missing_descriptors_are_unscorable(self):
        from workspace.vision.sift_match_multiplicity_probe import match_multiplicity
        self.assertEqual(match_multiplicity(None, None), {'scorable': False})
