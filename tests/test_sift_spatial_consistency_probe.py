import importlib.util
import unittest


@unittest.skipUnless(all(importlib.util.find_spec(n) for n in ('cv2','numpy','PIL')), 'optional vision dependencies')
class PositionedSiftTests(unittest.TestCase):
    def pair(self, transform=None, repeated=False):
        import numpy as np
        from workspace.vision.sift_spatial_consistency_probe import PositionedSift, descriptor_key
        probe = PositionedSift()
        q = np.random.default_rng(69).normal(0,30,(8,128)).astype('float32')
        r = q+.001
        points = np.array([[.2,.2],[.4,.2],[.6,.2],[.8,.2],[.2,.8],[.4,.8],[.6,.8],[.8,.8]], dtype='float32')
        if repeated:
            points[:] = [.5,.5]
        probe.positions[descriptor_key(q)] = points
        probe.positions[descriptor_key(r)] = transform(points) if transform else points.copy()
        return probe,q,r

    def test_frozen_descriptors_are_preserved(self):
        import numpy as np
        from PIL import Image
        from workspace.vision.public_meld_identity_sift import _sift_descriptors
        from workspace.vision.sift_spatial_consistency_probe import PositionedSift
        pixels = np.random.default_rng(69).integers(0,256,(96,72,3),dtype='uint8')
        image = Image.fromarray(pixels)
        actual = PositionedSift().extract(image)
        expected = _sift_descriptors(image)
        self.assertIsNotNone(expected)
        np.testing.assert_array_equal(actual, expected)

    def test_coherent_layout_survives_small_affine_change(self):
        probe,q,r=self.pair(lambda points: points*.98+.01)
        self.assertGreater(probe.score(q,r), 0)
        self.assertEqual(probe.last_audit['inliers'], 8)
        self.assertTrue(probe.last_audit['pattern_coverage_checked'])
        self.assertAlmostEqual(probe.last_audit['query_inlier_hull_fraction'], 1.0)
        self.assertAlmostEqual(probe.last_audit['reference_inlier_hull_fraction'], 1.0)
        self.assertEqual(probe.last_audit['query_unmatched_grid_cells'], [])
        self.assertEqual(probe.last_audit['reference_unmatched_grid_cells'], [])
        self.assertTrue(probe.last_audit['bidirectional_support_checked'])
        self.assertEqual(
            probe.last_audit['query_keypoints_supported_by_reference_fraction'],
            1.0,
        )
        self.assertEqual(
            probe.last_audit['reference_keypoints_supported_by_query_fraction'],
            1.0,
        )

    def test_reflected_layout_cannot_match_upright_pose(self):
        def reflected(points):
            copy=points.copy();copy[:,0]=1-copy[:,0];return copy
        probe,q,r=self.pair(reflected)
        self.assertEqual(probe.score(q,r), 0)
        self.assertEqual(probe.last_audit['reason'], 'implausible_normalized_affine')

    def test_one_location_is_not_whole_face_support(self):
        probe,q,r=self.pair(repeated=True)
        self.assertEqual(probe.score(q,r), 0)
        self.assertEqual(probe.last_audit['unique_position_pairs'], 1)

    def test_nearby_true_points_survive_distant_identical_distractors(self):
        import numpy as np
        from workspace.vision.sift_spatial_consistency_probe import PositionedSift, descriptor_key
        probe,q,_=self.pair()
        points=probe.positions[descriptor_key(q)]
        reference=np.concatenate((q+.1,q))
        reference_points=np.concatenate((points,np.roll(points,4,axis=0)))
        probe.positions[descriptor_key(reference)]=reference_points
        self.assertEqual(probe.score(q,reference), 0)
        probe.local_window=True
        self.assertGreater(probe.score(q,reference), 0)
        self.assertEqual(probe.last_audit['inliers'], 8)

    def test_coverage_audit_exposes_unmatched_reference_regions(self):
        import numpy as np
        from workspace.vision.sift_spatial_consistency_probe import _coverage_audit
        query = np.array([
            [.1,.1],[.5,.1],[.9,.1],
            [.1,.5],[.5,.5],[.9,.5],
            [.1,.9],[.5,.9],[.9,.9],
        ], dtype='float32')
        reference = query.copy()
        query_inliers = query[:6]
        reference_inliers = reference[:6]
        audit = _coverage_audit(
            query, reference, query_inliers, reference_inliers
        )
        self.assertLess(audit['reference_inlier_hull_fraction'], 1.0)
        self.assertEqual(
            audit['reference_unmatched_grid_cells'],
            [[0, 2], [1, 2], [2, 2]],
        )
        self.assertEqual(
            audit['query_unmatched_grid_cells'],
            [[0, 2], [1, 2], [2, 2]],
        )


    def test_bidirectional_support_exposes_unexplained_dense_reference(self):
        import numpy as np
        from workspace.vision.sift_spatial_consistency_probe import (
            _bidirectional_affine_support,
        )
        query = np.array([
            [.2,.2],[.5,.2],[.8,.2],
            [.2,.5],[.5,.5],[.8,.5],
        ], dtype='float32')
        reference = np.concatenate((
            query,
            np.array([[.2,.85],[.5,.85],[.8,.85]], dtype='float32'),
        ))
        identity = np.array([[1.,0.,0.],[0.,1.,0.]], dtype='float32')
        audit = _bidirectional_affine_support(
            query, reference, identity, radius=.05
        )
        self.assertEqual(
            audit['query_keypoints_supported_by_reference_fraction'],
            1.0,
        )
        self.assertLess(
            audit['reference_keypoints_supported_by_query_fraction'],
            1.0,
        )


if __name__ == "__main__":
    unittest.main()
