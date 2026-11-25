"""Synthetic fail-closed tests for #69 action-area onset candidates."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import unittest

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None

from workspace.vision.public_action_area_onset import (
    ActionAreaProfile, collapse_action_area_onset_candidates,
    probe_action_area_onset,
)
from workspace.vision.public_meld_gap_onset import SourceScopedOpticalFrame

SHA = "a" * 64


def profile(actor="player"):
    return ActionAreaProfile(
        actor=actor,
        onset_region=(.45, .35, .45, .45),
        confirmation_region=(.25, .25, .65, .60),
        width_ratio=(.035, .09),
        height_ratio=(.07, .16),
        area_ratio=(.002, .012),
        aspect_ratio=(.9, 2.2),
        centroid_motion_ratio=(.02, .5),
    )


def pixels(*, tile=None, second_tile=False, width=960, height=448):
    image = np.empty((height, width, 3), dtype=np.uint8)
    image[:] = (130, 92, 18)
    # Persistent public row: unchanged pixels must not become an onset.
    image[round(height*.39):round(height*.51),
          round(width*.25):round(width*.67)] = (222, 222, 222)
    if tile is not None:
        x, y = tile
        image[y:y+58, x:x+46] = (224, 224, 224)
    if second_tile:
        image[210:268, 740:786] = (224, 224, 224)
    return image


def optical(image, index, **overrides):
    values = dict(
        source_session="synthetic_source",
        source_sha256=SHA,
        stream_epoch=2,
        frame_index=index,
        decoded_pixel_sha256=hashlib.sha256(image.tobytes()).hexdigest(),
        bgr_pixels=image,
        original_video_sha_verified=True,
        original_decoded_frame_verified=True,
    )
    values.update(overrides)
    return SourceScopedOpticalFrame(**values)


def run(a, b, c, *, p=None, **options):
    opts = dict(
        profile=p or profile(),
        action_regions_independently_verified=True,
        source_frames_unobscured=True,
    )
    opts.update(options)
    return probe_action_area_onset(
        optical(a, 100), optical(b, 101), optical(c, 102), **opts,
    )


@unittest.skipUnless(np is not None and cv2 is not None,
                     "OpenCV/numpy Vision extras not installed")
class ActionAreaOnsetTests(unittest.TestCase):
    def test_new_moving_tile_shape_is_candidate_only(self):
        out = run(pixels(), pixels(tile=(620, 250)), pixels(tile=(500, 220)))
        self.assertEqual(out.status, "ACTION_AREA_ONSET_CANDIDATE_ONLY")
        self.assertEqual(out.region_actor_hint, "player")
        self.assertEqual(out.first_visible_frame, 101)
        payload = out.to_dict()
        self.assertEqual(payload["region_actor_hint"], "player")
        self.assertEqual(payload["tile_identity"], "UNKNOWN")
        self.assertEqual(payload["actual_action_kind"], "UNKNOWN")
        self.assertEqual(payload["actual_actor"], "UNKNOWN")
        self.assertTrue(payload["river_or_meld_join_required"])
        self.assertFalse(payload["safe_for_runtime"])
        self.assertFalse(payload["safe_for_executor"])
        self.assertNotIn(SHA, str(payload))
        self.assertNotIn("synthetic_source", str(payload))
        self.assertNotIn("101", str(payload))

    def test_persistent_or_absent_shape_is_not_new_onset(self):
        for before, first, confirm in (
            (pixels(), pixels(), pixels()),
            (pixels(tile=(620, 250)), pixels(tile=(620, 250)), pixels(tile=(500, 220))),
        ):
            with self.subTest():
                self.assertEqual(run(before, first, confirm).status, "UNKNOWN")

    def test_single_frame_flash_without_confirmation_abstains(self):
        out = run(pixels(), pixels(tile=(620, 250)), pixels())
        self.assertEqual(out.status, "UNKNOWN")
        self.assertIn("confirmation", out.reason)

    def test_source_profile_can_reject_stationary_shade_change(self):
        out = run(
            pixels(), pixels(tile=(620, 250)), pixels(tile=(620, 250)),
        )
        self.assertEqual(out.status, "UNKNOWN")
        self.assertIn("motion", out.reason)

    def test_multiple_tile_shapes_are_ambiguous(self):
        out = run(
            pixels(), pixels(tile=(620, 250), second_tile=True),
            pixels(tile=(500, 220), second_tile=True),
        )
        self.assertEqual(out.status, "UNKNOWN")
        self.assertIn("ambiguous", out.reason)

    def test_source_region_and_frame_lineage_fail_closed(self):
        a = optical(pixels(), 100)
        b = optical(pixels(tile=(620, 250)), 101)
        c = optical(pixels(tile=(500, 220)), 102)
        for replacement in (
            (b, {"source_sha256": "b" * 64}),
            (b, {"source_session": "other"}),
            (b, {"stream_epoch": 3}),
            (b, {"frame_index": 104}),
            (c, {"frame_index": 103}),
            (b, {"original_video_sha_verified": False}),
            (b, {"decoded_pixel_sha256": "b" * 64}),
        ):
            frame, patch = replacement
            frames = [a, b, c]
            frames[frames.index(frame)] = replace(frame, **patch)
            out = probe_action_area_onset(
                *frames, profile=profile(),
                action_regions_independently_verified=True,
                source_frames_unobscured=True,
            )
            self.assertEqual(out.status, "UNKNOWN")
        for key in ("action_regions_independently_verified", "source_frames_unobscured"):
            opts = dict(action_regions_independently_verified=True,
                        source_frames_unobscured=True)
            opts[key] = False
            self.assertEqual(probe_action_area_onset(
                a, b, c, profile=profile(), **opts,
            ).status, "UNKNOWN")

    def test_invalid_profile_resolution_and_identical_first_frame_abstain(self):
        a, b, c = pixels(), pixels(tile=(620, 250)), pixels(tile=(500, 220))
        invalid = replace(profile(), actor="UNKNOWN")
        self.assertEqual(run(a, b, c, p=invalid).status, "UNKNOWN")
        self.assertEqual(run(a, np.copy(a), c).status, "UNKNOWN")
        tiny_a = pixels(width=300, height=200)
        tiny_b = np.copy(tiny_a); tiny_b[90:150, 180:225] = 224
        tiny_c = np.copy(tiny_a); tiny_c[80:140, 150:195] = 224
        self.assertEqual(run(tiny_a, tiny_b, tiny_c).status, "UNKNOWN")

    def test_region_actor_hint_never_becomes_actual_actor(self):
        out = run(
            pixels(), pixels(tile=(620, 250)), pixels(tile=(500, 220)),
            p=replace(profile(), actor="opponent"),
        )
        self.assertEqual(out.region_actor_hint, "opponent")
        self.assertEqual(out.to_dict()["actual_actor"], "UNKNOWN")

    def test_animation_burst_collapses_to_first_visible_candidate(self):
        a = run(pixels(), pixels(tile=(620, 250)), pixels(tile=(500, 220)))
        burst = tuple(replace(
            a, prior_frame=frame-1, first_visible_frame=frame,
            confirmation_frame=frame+1,
        ) for frame in (101, 102, 103, 104, 130))
        collapsed = collapse_action_area_onset_candidates(burst)
        self.assertEqual([x.first_visible_frame for x in collapsed], [101, 130])
        self.assertTrue(all(x.to_dict()["actual_action_kind"] == "UNKNOWN"
                            for x in collapsed))

    def test_candidate_collapse_rejects_mixed_source_actor_and_bad_order(self):
        a = run(pixels(), pixels(tile=(620, 250)), pixels(tile=(500, 220)))
        with self.assertRaises(ValueError):
            collapse_action_area_onset_candidates((a, replace(
                a, source_session="other", first_visible_frame=130,
            )))
        with self.assertRaises(ValueError):
            collapse_action_area_onset_candidates((a, replace(
                a, region_actor_hint="opponent", first_visible_frame=130,
            )))
        with self.assertRaises(ValueError):
            collapse_action_area_onset_candidates((a, a))
        for invalid in (True, 1, 0, -2):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    collapse_action_area_onset_candidates(
                        (a,), minimum_event_separation_frames=invalid,
                    )


if __name__ == "__main__":
    unittest.main()
