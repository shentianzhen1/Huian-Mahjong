"""#69 exploratory optical separator: no original video in public CI."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import unittest

AVAILABLE = all(importlib.util.find_spec(name) is not None
                for name in ("cv2", "numpy"))
SHA = "a" * 64
GROUP = (80, 60, 120, 70)


@unittest.skipUnless(AVAILABLE, "Optional Vision numpy/cv2 not installed")
class SourceBoundOpticalGapTests(unittest.TestCase):
    def setUp(self):
        import numpy as np
        from workspace.vision.public_meld_gap_onset import (
            SourceScopedOpticalFrame, probe_adjacent_group_gap,
        )
        self.np = np
        self.Frame = SourceScopedOpticalFrame
        self.probe = probe_adjacent_group_gap

    def canvas(self, *, group_gap=False, prior_separator=False):
        np = self.np
        pixels = np.empty((200, 500, 3), dtype=np.uint8)
        pixels[:] = (70, 90, 26)  # Teal/green source game background.
        pixels[60:130, 60:395, :] = (208, 208, 208)
        if group_gap or prior_separator:
            pixels[60:130, 200:236, :] = (70, 90, 26)
        return pixels

    def source(self, index, pixels, **changes):
        values = {
            "source_session": "synthetic_private_video_negative_control",
            "source_sha256": SHA,
            "stream_epoch": 3,
            "frame_index": index,
            "decoded_pixel_sha256": hashlib.sha256(
                pixels.tobytes()
            ).hexdigest(),
            "bgr_pixels": pixels,
            "original_video_sha_verified": True,
            "original_decoded_frame_verified": True,
        }
        values.update(changes)
        return self.Frame(**values)

    def run_probe(self, pre=None, post=None, **kwargs):
        if pre is None:
            pre = self.canvas()
        if post is None:
            post = self.canvas(group_gap=True)
        before, after = self.source(100, pre), self.source(101, post)
        params = {
            "approved_late_group_bbox": GROUP,
            "public_meld_roi_independently_verified": True,
            "late_group_bbox_source_locked": True,
        }
        params.update(kwargs)
        return self.probe(before, after, **params)

    def test_new_edge_gap_is_only_weak_development_candidate(self):
        out = self.run_probe()
        self.assertEqual(
            out.status, "NEW_EDGE_GAP_DEVELOPMENT_CANDIDATE_ONLY"
        )
        self.assertLess(out.longest_pre_gap_px, 14)
        self.assertGreaterEqual(out.longest_post_gap_px, 14)
        payload = out.to_dict()
        self.assertEqual(payload["real_action_kind"], "UNKNOWN")
        self.assertEqual(payload["incoming_tile"], "UNKNOWN")
        self.assertFalse(payload["safe_for_runtime"])
        self.assertFalse(payload["safe_for_executor"])
        self.assertFalse(payload["hand_shadow_used_as_eligibility_signal"])
        self.assertNotIn(SHA, str(payload))
        self.assertNotIn("synthetic_private_video", str(payload))

    def test_prior_flower_row_or_old_meld_separator_fails_closed(self):
        pre = self.canvas(prior_separator=True)
        post = self.canvas(group_gap=True)
        post[0, 0, 0] += 1  # Distinct decoded source frames, same edge gap.
        out = self.run_probe(pre, post)
        self.assertEqual(out.status, "UNKNOWN")
        self.assertIn("existing_separator", out.reason)

    def test_no_gap_or_tiny_gap_must_not_be_promoted(self):
        pre, post = self.canvas(), self.canvas()
        post[60:130, 200:205] = (70, 90, 26)
        self.assertEqual(self.run_probe(pre, post).status, "UNKNOWN")
        self.assertEqual(
            self.run_probe(gap_min_px=100).status, "UNKNOWN",
        )

    def test_source_sha_and_consecutive_decoded_frames_required(self):
        pre, post = self.canvas(), self.canvas(group_gap=True)
        good_a, good_b = self.source(100, pre), self.source(101, post)
        for replacement in (
            {"source_session": "second_original_video"},
            {"source_sha256": "b" * 64},
            {"stream_epoch": 4},
            {"frame_index": 104},
            {"decoded_pixel_sha256": "c" * 64},
            {"original_video_sha_verified": False},
            {"original_decoded_frame_verified": False},
        ):
            with self.subTest(replacement=replacement):
                self.assertEqual(
                    self.probe(
                        good_a, replace(good_b, **replacement),
                        approved_late_group_bbox=GROUP,
                        public_meld_roi_independently_verified=True,
                        late_group_bbox_source_locked=True,
                    ).status,
                    "UNKNOWN",
                )

    def test_pixel_bytes_invariant_and_invalid_dtype_fail_closed(self):
        bad = self.canvas(group_gap=True).astype("float32")
        self.assertEqual(
            self.run_probe(post=bad).status, "UNKNOWN",
        )
        different_shape = self.canvas(group_gap=True)[:-1]
        self.assertEqual(
            self.run_probe(post=different_shape).status, "UNKNOWN",
        )
        frame = self.canvas()
        self.assertEqual(
            self.run_probe(pre=frame, post=frame.copy()).status,
            "UNKNOWN",
        )

    def test_public_roi_must_be_independently_bound_not_hand_shadow(self):
        for attrs in (
            {"public_meld_roi_independently_verified": False},
            {"late_group_bbox_source_locked": False},
            {"approved_late_group_bbox": (10, 20, 30, 30)},
            {"approved_late_group_bbox": (490, 60, 120, 70)},
            {"approved_late_group_bbox": [80, 60, 120, 70]},
        ):
            with self.subTest(attrs=attrs):
                self.assertEqual(self.run_probe(**attrs).status, "UNKNOWN")

    def test_same_original_replay_is_valid_for_geometry_not_live_buttons(self):
        out = self.run_probe()
        self.assertEqual(
            out.status, "NEW_EDGE_GAP_DEVELOPMENT_CANDIDATE_ONLY",
        )
        self.assertTrue(out.to_dict()["public_meld_region_independently_required"])

    def test_bad_gap_parameter_rejected_instead_of_defaulting(self):
        for n in (True, 0, -5, 2.5):
            with self.subTest(n=n):
                with self.assertRaises(ValueError):
                    self.run_probe(gap_min_px=n)

    def test_existing_broad_gap_never_counts_as_new_without_group_onset(self):
        pre = self.canvas(prior_separator=True)
        post = self.canvas(group_gap=True)
        post[0, 0, 0] += 1
        self.assertEqual(
            self.run_probe(pre, post).status, "UNKNOWN",
        )


if __name__ == "__main__":
    unittest.main()
