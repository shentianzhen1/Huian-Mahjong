"""Frame provenance checks require no private footage or Vision dependencies."""
import unittest

from workspace.vision.verified_frame_lineage import verify_frame_lineage


class VerifiedFrameLineageTests(unittest.TestCase):
    def test_vfr_contiguous_clip_with_small_timebase_rounding(self):
        source = (1.0, 1.016667, 1.050, 1.066667, 1.100, 1.116667)
        clip = (.0003, .0164, .0503)
        result = verify_frame_lineage(
            source, clip, source_first_frame=2, expected_timestamp_offset=1.05,
            tolerance_seconds=.001, sample_frames=(0, 2))
        self.assertEqual(result["source_frame_range"], [2, 4])
        self.assertEqual(result["sample_frame_mapping"]["2"]["source_frame"], 4)
        self.assertFalse(result["pixel_identity_verified"])
        self.assertFalse(result["action_accuracy_verified"])

    def test_wrong_start_dropped_frame_and_invalid_pts_abort(self):
        source = (1.0, 1.016667, 1.050, 1.066667, 1.100, 1.116667)
        clip = (.0003, .0503, .0664)
        with self.assertRaisesRegex(ValueError, "frame lineage mismatch"):
            verify_frame_lineage(source, clip, source_first_frame=2,
                                 expected_timestamp_offset=1.05,
                                 tolerance_seconds=.001)
        with self.assertRaisesRegex(ValueError, "frame lineage mismatch"):
            verify_frame_lineage(source, (.0003, .0169), source_first_frame=1,
                                 expected_timestamp_offset=1.05,
                                 tolerance_seconds=.001)
        with self.assertRaisesRegex(ValueError, "increasing"):
            verify_frame_lineage(source, (0., 0.), source_first_frame=2,
                                 expected_timestamp_offset=1.05)
        with self.assertRaisesRegex(ValueError, "outside verified"):
            verify_frame_lineage(source, (.0003,), source_first_frame=2,
                                 expected_timestamp_offset=1.05,
                                 sample_frames=(1,))


if __name__ == "__main__":
    unittest.main()
