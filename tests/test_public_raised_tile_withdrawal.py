"""#69 exploratory upper public tile withdrawal; synthetic, not accuracy."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import unittest

try:
    import numpy as np
    import cv2
except ImportError:
    np = None
    cv2 = None

from workspace.vision.public_meld_gap_onset import SourceScopedOpticalFrame
from workspace.vision.public_raised_tile_withdrawal import (
    probe_adjacent_raised_tile_withdrawal,
)

SHA = "a" * 64


def synthetic_frame(*, width=960, height=448, upper=True, extra=False):
    if np is None:
        raise RuntimeError("numpy optional Vision dependency required")
    image = np.empty((height, width, 3), dtype=np.uint8)
    image[:] = (130, 92, 18)  # Dark saturated teal, not paper.
    # The persistent flat public river remains before and after.
    left = round(width * .43)
    right = round(width * .65)
    y = round(height * .23)
    image[y:y+round(height*.065), left:right] = (219, 221, 220)
    if upper:
        x = left + round(width * .02)
        start = round(height * .09)
        # Tall upper offered/public single touches the persistent row.
        image[start:y+5, x:x+round(width * .052)] = (222, 222, 222)
    if extra:
        # An unrelated second tall paper-like component makes the source
        # ambiguous; fail closed instead of assigning a claimed tile.
        start = round(height * .09)
        image[start:start+round(height * .17),
              round(width * .32):round(width * .37)] = (222, 222, 222)
    return image


def optical(image, index, **kwargs):
    attrs = dict(
        source_session="synthetic_original_source",
        source_sha256=SHA,
        stream_epoch=2,
        frame_index=index,
        decoded_pixel_sha256=hashlib.sha256(image.tobytes()).hexdigest(),
        bgr_pixels=image,
        original_video_sha_verified=True,
        original_decoded_frame_verified=True,
    )
    attrs.update(kwargs)
    return SourceScopedOpticalFrame(**attrs)


def run(a, b, *, at=100, **kwargs):
    opts = dict(
        upper_public_action_region_verified=True,
        source_frames_unobscured_in_upper_region=True,
    )
    opts.update(kwargs)
    return probe_adjacent_raised_tile_withdrawal(
        optical(a, at), optical(b, at+1), **opts,
    )


@unittest.skipUnless(np is not None and cv2 is not None,
                     "OpenCV/numpy Vision extras not installed")
class RaisedPublicTileWithdrawalTests(unittest.TestCase):

    def test_adjacent_upper_component_withdrawal_at_both_reviewed_resolutions(self):
        for w, h in ((960, 448), (1046, 480)):
            with self.subTest(resolution=(w, h)):
                prior = synthetic_frame(width=w, height=h)
                after = synthetic_frame(width=w, height=h, upper=False)
                x = run(prior, after)
                self.assertEqual(
                    x.status,
                    "PUBLIC_RAISED_TILE_WITHDRAWAL_OPTICAL_CANDIDATE_ONLY",
                )
                self.assertEqual(x.prior_candidates, 1)
                self.assertEqual(x.after_candidates, 0)
                self.assertEqual(x.after_frame - x.prior_frame, 1)
                self.assertEqual(x.source_session, "synthetic_original_source")
                self.assertEqual(x.source_sha256, SHA)
                self.assertEqual(x.stream_epoch, 2)
                out = x.to_dict()
                self.assertEqual(out["actual_discard_identity"], "UNKNOWN")
                self.assertEqual(out["production_action_kind"], "UNKNOWN")
                self.assertFalse(out["owner_confirmed_action"])
                self.assertFalse(out["source_disjoint_promotion"])
                self.assertFalse(out["concealed_hand_shadow_used"])
                self.assertFalse(out["replay_buttons_used"])
                self.assertFalse(out["safe_for_runtime"])
                self.assertFalse(out["safe_for_executor"])
                self.assertNotIn(SHA, str(out))
                self.assertNotIn("synthetic_original_source", str(out))

    def test_upper_component_still_present_is_negative_control(self):
        prior = synthetic_frame()
        after = np.copy(prior)
        # Same source-frame consecutive indices but different decoded pixels
        # from unrelated animation: upper raised public tile still exists.
        after[320:330, 10:20] = 0
        x = run(prior, after)
        self.assertEqual(x.status, "UNKNOWN")
        self.assertIn("still_present", x.reason)

    def test_both_frames_have_no_prior_raised_component(self):
        a = synthetic_frame(upper=False)
        b = np.copy(a)
        b[320:330, 10:20] = 0
        x = run(a, b)
        self.assertEqual(x.status, "UNKNOWN")
        self.assertIn("none_or_ambiguous", x.reason)

    def test_multiple_tall_public_candidates_refuse_identity(self):
        a = synthetic_frame(extra=True)
        b = synthetic_frame(upper=False)
        x = run(a, b)
        self.assertEqual(x.status, "UNKNOWN")
        self.assertEqual(x.prior_candidates, 2)

    def test_identical_source_pixels_do_not_mean_withdrawal(self):
        a = synthetic_frame()
        x = run(a, np.copy(a))
        self.assertEqual(x.status, "UNKNOWN")
        self.assertIn("identical", x.reason)

    def test_public_region_and_overlay_must_be_verified_independently(self):
        before = synthetic_frame()
        after = synthetic_frame(upper=False)
        for opts in (
            {"upper_public_action_region_verified": False},
            {"source_frames_unobscured_in_upper_region": False},
        ):
            with self.subTest(opts=opts):
                x = run(before, after, **opts)
                self.assertEqual(x.status, "UNKNOWN")

    def test_source_sha_session_epoch_and_frame_gap_fail_closed(self):
        a = optical(synthetic_frame(), 100)
        b = optical(synthetic_frame(upper=False), 101)
        for patch in (
            {"source_sha256": "b" * 64},
            {"source_session": "second_original_match"},
            {"stream_epoch": 3},
            {"frame_index": 104},
            {"frame_index": 100},
        ):
            with self.subTest(patch=patch):
                x = probe_adjacent_raised_tile_withdrawal(
                    a, replace(b, **patch),
                    upper_public_action_region_verified=True,
                    source_frames_unobscured_in_upper_region=True,
                )
                self.assertEqual(x.status, "UNKNOWN")

    def test_false_source_pixel_attestation_and_tamper_refused(self):
        a = optical(synthetic_frame(), 100)
        b = optical(synthetic_frame(upper=False), 101)
        for patch in (
            {"original_video_sha_verified": False},
            {"original_decoded_frame_verified": False},
            {"decoded_pixel_sha256": "b" * 64},
            {"bgr_pixels": np.copy(b.bgr_pixels).astype(np.float32)},
        ):
            with self.subTest(patch=str(patch.keys())):
                x = probe_adjacent_raised_tile_withdrawal(
                    a, replace(b, **patch),
                    upper_public_action_region_verified=True,
                    source_frames_unobscured_in_upper_region=True,
                )
                self.assertEqual(x.status, "UNKNOWN")

    def test_resolution_change_and_unsupported_tiny_frames_abstain(self):
        a = optical(synthetic_frame(), 100)
        b = optical(synthetic_frame(width=1046, height=480, upper=False), 101)
        x = probe_adjacent_raised_tile_withdrawal(
            a, b, upper_public_action_region_verified=True,
            source_frames_unobscured_in_upper_region=True,
        )
        self.assertEqual(x.status, "UNKNOWN")
        a = synthetic_frame(width=300, height=200)
        b = synthetic_frame(width=300, height=200, upper=False)
        self.assertEqual(run(a, b).status, "UNKNOWN")

    def test_competing_optical_cue_still_not_a_claim(self):
        # A real-looking change may reflect UI animation: this probe can
        # NEVER assert CHI, PENG, KONG, PASS, or claimed incoming tile.
        out = run(synthetic_frame(),
                  synthetic_frame(upper=False)).to_dict()
        self.assertEqual(out["actual_claimed_meld"], "UNKNOWN")
        self.assertEqual(out["actual_discard_identity"], "UNKNOWN")
        self.assertFalse(out["owner_confirmed_action"])


if __name__ == "__main__":
    unittest.main()
