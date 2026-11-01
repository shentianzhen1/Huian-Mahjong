"""Issue #69: delayed shade is FOLLOW-UP evidence, not action onset."""
from __future__ import annotations

from dataclasses import replace
import unittest

from workspace.vision.public_meld_delayed_shade_review import (
    SourceScopedShadeFrame, review_delayed_shade,
)

SOURCE = "a" * 64


def sequence(*indices, frame0=120, step=1):
    return [
        SourceScopedShadeFrame(
            source_session="synthetic_verified_session",
            source_sha256=SOURCE,
            stream_epoch=1,
            meld_track_id="reviewed_regular_group_1",
            frame_index=frame0 + i * step,
            shadow_index=position,
            reviewed_public_meld=True,
            regular_three_faces=True,
            exact_source_frame_verified=True,
        )
        for i, position in enumerate(indices)
    ]


class DelayedMeldShadeReviewTests(unittest.TestCase):
    def test_actual_shade_delay_measured_from_group_not_action(self):
        frames = sequence(None, None, None, 1, 1, 1)
        result = review_delayed_shade(
            frames,
            group_history="newly_observed",
            verified_video_fps=30.0,
        )
        self.assertEqual(result.status, "DELAYED_SHADE_AFTER_MELD_APPEARANCE")
        self.assertEqual(result.shadow_index, 1)
        self.assertEqual(result.meld_first_observed_frame, 120)
        self.assertEqual(result.shade_first_observed_frame, 123)
        self.assertEqual(result.observed_lag_frames, 3)
        self.assertEqual(result.observed_lag_seconds, 0.1)
        payload = result.to_dict()
        self.assertEqual(payload["action_kind"], "UNKNOWN")
        self.assertEqual(payload["incoming_tile_id"], "UNKNOWN")
        self.assertIsNone(payload["actual_action_frame"])
        self.assertIsNone(payload["actual_action_to_shade_delay"])
        self.assertFalse(payload["independently_verified_preceding_discard"])
        self.assertFalse(payload["safe_for_runtime"])
        self.assertFalse(payload["safe_for_executor"])

    def test_existing_group_darkens_later_but_does_not_create_a_new_action(self):
        # Existing G12 development observation: earlier unshaded row,
        # then one darkened slot. Timing of appearance is NOT an action.
        result = review_delayed_shade(
            sequence(None, None, 0, 0),
            group_history="pre_existing",
            verified_video_fps=29.0,
        )
        self.assertEqual(
            result.status,
            "PRE_EXISTING_GROUP_SHADE_CHANGE_UNATTRIBUTED",
        )
        self.assertEqual(result.shadow_index, 0)
        self.assertEqual(result.observed_lag_frames, 2)
        self.assertIn("not_a_new_action", result.issues[0])
        self.assertEqual(result.to_dict()["action_kind"], "UNKNOWN")

    def test_unknown_group_history_never_becomes_new_meld_fact(self):
        result = review_delayed_shade(sequence(None, None, 2, 2))
        self.assertEqual(result.status, "DELAYED_SHADE_GROUP_HISTORY_UNKNOWN")
        self.assertEqual(result.shadow_index, 2)
        self.assertIsNone(result.observed_lag_seconds)
        self.assertFalse(result.to_dict()["formal_promotion_evidence"])

    def test_existing_shade_on_first_frame_is_left_censored(self):
        result = review_delayed_shade(
            sequence(1, 1, 1),
            group_history="newly_observed",
        )
        self.assertEqual(result.status, "SHADE_ALREADY_PRESENT")
        self.assertIsNone(result.shadow_index)
        self.assertIsNone(result.observed_lag_frames)
        self.assertIn("unshaded_baseline", result.issues[0])

    def test_one_frame_flicker_or_continued_no_shade_abstains(self):
        for frames in (
            sequence(None, 0, None, 0, None),
            sequence(None, None, None, None),
            sequence(None, 2),
        ):
            with self.subTest(frames=[f.shadow_index for f in frames]):
                result = review_delayed_shade(
                    frames, group_history="newly_observed"
                )
                self.assertEqual(result.status, "PENDING_OR_ABSTAINED")
                self.assertIsNone(result.shadow_index)

    def test_gap_resets_streak_without_assuming_fixed_animation_time(self):
        # Frames sampled at 5-frame intervals cannot be called consecutive
        # unless caller explicitly validates that sampling cadence.
        frames = sequence(None, None, 0, 0, step=5)
        result = review_delayed_shade(frames)
        self.assertEqual(result.status, "PENDING_OR_ABSTAINED")
        authorized_spacing = review_delayed_shade(
            frames, max_gap_frames=5, group_history="newly_observed"
        )
        self.assertEqual(authorized_spacing.shadow_index, 0)
        self.assertEqual(authorized_spacing.observed_lag_frames, 10)
        self.assertIsNone(authorized_spacing.observed_lag_seconds)

    def test_conflicting_later_stable_shade_positions_abstain(self):
        result = review_delayed_shade(
            sequence(None, 0, 0, None, 2, 2),
            group_history="newly_observed",
        )
        self.assertEqual(result.status, "UNKNOWN")
        self.assertIsNone(result.shadow_index)
        self.assertIn("conflicting", result.issues[0])

    def test_cross_video_epoch_or_track_never_correlates(self):
        frames = sequence(None, 1, 1)
        for tamper in (
            {"source_session": "other_session"},
            {"source_sha256": "b" * 64},
            {"stream_epoch": 2},
            {"meld_track_id": "different_group"},
            {"frame_index": frames[0].frame_index},
        ):
            with self.subTest(tamper=tamper):
                changed = [frames[0], replace(frames[1], **tamper), frames[2]]
                result = review_delayed_shade(changed)
                self.assertEqual(result.status, "UNKNOWN")
                self.assertEqual(result.to_dict()["action_kind"], "UNKNOWN")

    def test_gold_concealed_hand_and_unverified_source_abstain(self):
        for tamper in (
            {"reviewed_public_meld": False},
            {"regular_three_faces": False},
            {"exact_source_frame_verified": False},
            {"shadow_index": 3},
        ):
            with self.subTest(tamper=tamper):
                frames = sequence(None, 1, 1)
                frames[1] = replace(frames[1], **tamper)
                result = review_delayed_shade(frames)
                self.assertEqual(result.status, "UNKNOWN")
                self.assertIsNone(result.shadow_index)
                self.assertFalse(result.to_dict()["safe_for_executor"])

    def test_no_source_and_invalid_sampling_parameters_fail_closed(self):
        self.assertEqual(
            review_delayed_shade([]).status, "UNKNOWN"
        )
        with self.assertRaisesRegex(ValueError, "temporal stability"):
            review_delayed_shade(sequence(None, 1, 1),
                                 minimum_stable_observations=1)
        with self.assertRaisesRegex(ValueError, "temporal stability"):
            review_delayed_shade(sequence(None, 1, 1), max_gap_frames=0)
        with self.assertRaisesRegex(ValueError, "video FPS"):
            review_delayed_shade(sequence(None, 1, 1),
                                 verified_video_fps=float("nan"))
        with self.assertRaisesRegex(ValueError, "group_history"):
            review_delayed_shade(sequence(None, 1, 1),
                                 group_history="just_chi")


if __name__ == "__main__":
    unittest.main()
