import unittest
import hashlib
import importlib.util
from pathlib import Path
from unittest.mock import patch

from workspace.vision.tiles_runtime_v0_2.whole_hand_baseline_export import (
    _align_exact_counts,
    _sample_summary,
    _read_burst,
    _verify_reviewed_frame,
)
from workspace.vision.tiles_runtime_v0_2.whole_hand_eval import (
    FROZEN_CONFIDENCE_THRESHOLD,
)


def _component(x, region, candidate, accepted, confidence=0.9):
    return {
        "pixel_bbox": [x, 400, 40, 70],
        "classification_crop_bbox": [x, 400, 40, 70],
        "region_candidate": region,
        "frame": 100,
        "candidate_tile_id": candidate,
        "tile_id": accepted,
        "tile_confidence": confidence,
        "identity_reason": "accepted" if accepted != "UNKNOWN" else "below_confidence_threshold",
        "private_crop_ref": f"{region}-{x}.png",
    }


class WholeHandBaselineExportTests(unittest.TestCase):
    def test_reviewed_rgb_binding_rejects_wrong_or_implicit_frame(self):
        class Pixels:
            def convert(self, mode): return self
            def tobytes(self): return b'reviewed RGB pixels'
        pixels = Pixels()
        sample = {'source_frame':7,'reviewed_frame_rgb_sha256':hashlib.sha256(pixels.tobytes()).hexdigest()}
        _verify_reviewed_frame(sample,[7],[pixels])
        with self.assertRaisesRegex(ValueError,'does not match'):
            _verify_reviewed_frame({**sample,'reviewed_frame_rgb_sha256':'0'*64},[7],[pixels])
        with self.assertRaisesRegex(ValueError,'explicit source_frame'):
            _verify_reviewed_frame({**sample,'source_frame':None},[7],[pixels])

    @unittest.skipUnless(importlib.util.find_spec('cv2') and importlib.util.find_spec('PIL'),
                         'Vision dependencies required for decoder contract')
    def test_explicit_frame_uses_sequential_ordinals_without_random_seek(self):
        import cv2
        import numpy as np
        class Capture:
            def __init__(self): self.position=0; self.closed=False
            def isOpened(self): return True
            def get(self,key): return 10 if key == cv2.CAP_PROP_FRAME_COUNT else 1
            def set(self,*args): raise AssertionError('random seek would return wrong VFR pixels')
            def grab(self): self.position+=1; return True
            def read(self):
                pixels=np.full((2,3,3),self.position,dtype=np.uint8)
                self.position+=1
                return True,pixels
            def release(self): self.closed=True
        capture=Capture()
        with patch('cv2.VideoCapture',return_value=capture):
            ids,images,metadata=_read_burst(Path('private.mov'),0,source_frame=5)
        self.assertEqual(ids,[3,4,5,6,7])
        self.assertEqual([im.getpixel((0,0))[0] for im in images],ids)
        self.assertEqual(metadata['decoded_size'],[3,2])
        self.assertEqual(metadata['frame_access'],'sequential_decoded_ordinal')
        self.assertTrue(capture.closed)

    def test_threshold_remains_frozen_at_point_82(self):
        self.assertEqual(FROZEN_CONFIDENCE_THRESHOLD, 0.82)

    def test_exact_counts_align_left_to_right_and_keep_draw_separate(self):
        sample = {
            "truth": {
                "concealed_hand": ["M1", "M2"],
                "draw_visual": "P9",
            }
        }
        components = [
            _component(80, "hand", "M2", "M2"),
            _component(250, "draw_visual", "P9", "P9"),
            _component(20, "hand", "M1", "M1"),
        ]

        alignment = _align_exact_counts(sample, components)

        self.assertEqual(
            alignment["status"],
            "exact_count_left_to_right_alignment_pending_crop_review",
        )
        self.assertEqual(
            [(row["region"], row["truth_tile"]) for row in alignment["slots"]],
            [("hand", "M1"), ("hand", "M2"), ("draw_visual", "P9")],
        )
        self.assertTrue(all(row["crop_status"] == "unreviewed" for row in alignment["slots"]))

    def test_count_mismatch_never_shifts_truth_into_fake_classifier_errors(self):
        sample = {
            "truth": {
                "concealed_hand": ["M1", "M2", "M3"],
                "draw_visual": None,
            }
        }
        components = [
            _component(20, "hand", "M1", "M1"),
            _component(80, "hand", "M3", "M3"),
        ]

        alignment = _align_exact_counts(sample, components)

        self.assertEqual(alignment["status"], "manual_alignment_required")
        self.assertEqual(alignment["truth_hand_count"], 3)
        self.assertEqual(alignment["detected_hand_count"], 2)
        self.assertEqual(alignment["slots"], [])

    def test_pre_review_summary_keeps_rejection_distinct_from_wrong_accept(self):
        alignment = {
            "status": "exact_count_left_to_right_alignment_pending_crop_review",
            "slots": [
                {"truth_tile": "M1", "accepted_tile_id": "M1"},
                {"truth_tile": "M2", "accepted_tile_id": "M3"},
                {"truth_tile": "M4", "accepted_tile_id": "UNKNOWN"},
            ],
        }
        summary = _sample_summary(alignment, {"geometry_untrusted": False})

        self.assertEqual(summary["accepted_exact_before_crop_review"], 1)
        self.assertEqual(summary["accepted_wrong_before_crop_review"], 1)
        self.assertEqual(summary["rejected_before_crop_review"], 1)
        self.assertTrue(summary["crop_review_required"])


if __name__ == "__main__":
    unittest.main()
