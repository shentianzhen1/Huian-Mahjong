"""Strict public discard + newly exposed meld + DELAYED shade contracts."""
from __future__ import annotations

from dataclasses import replace
import unittest

from workspace.vision.public_meld_action_cross_evidence import (
    ManuallyReviewedNewMeld,
    ManuallyReviewedPublicDiscard,
    cross_check_reviewed_meld_event,
)
from workspace.vision.public_meld_delayed_shade_review import (
    SourceScopedShadeFrame,
)

SHA = "a" * 64


def bundle(
    ids=("P4", "P5", "P6"),
    claimed="P6",
    shade_index=2,
    discard_at=101,
    meld_at=122,
    shade_at=131,
):
    discard = ManuallyReviewedPublicDiscard(
        source_session="reviewed_original_1",
        source_sha256=SHA,
        stream_epoch=1,
        frame_index=discard_at,
        screen_side="upper",
        visible_tile_id=claimed,
        original_video_sha_verified=True,
        source_frame_pixel_verified=True,
        explicit_tile_manually_reviewed=True,
        no_intervening_public_action_reviewed=True,
    )
    meld = ManuallyReviewedNewMeld(
        source_session="reviewed_original_1",
        source_sha256=SHA,
        stream_epoch=1,
        meld_track_id="stable_lower_regular_group",
        frame_index=meld_at,
        screen_side="lower",
        face_ids_left_to_right=ids,
        original_video_sha_verified=True,
        source_frame_pixel_verified=True,
        user_approved_face_id_provenance=True,
        independently_reviewed_absent_before_present=True,
    )
    frames = [
        SourceScopedShadeFrame(
            source_session="reviewed_original_1",
            source_sha256=SHA,
            stream_epoch=1,
            meld_track_id="stable_lower_regular_group",
            frame_index=f,
            shadow_index=shade_index if f >= shade_at else None,
            reviewed_public_meld=True,
            regular_three_faces=True,
            exact_source_frame_verified=True,
        )
        for f in range(meld_at, shade_at + 5)
    ]
    return discard, meld, frames


class ReviewedMeldCrossEvidenceTests(unittest.TestCase):
    def test_seven_types_of_existing_shaded_development_observations(self):
        # Synthetic contracts modeled on all 7 previously inspected private
        # case SHAPES. The private video, exact timestamps and label maps are
        # deliberately NOT part of public CI, and 7/7 is NOT blind accuracy.
        shapes = (
            (("P4", "P5", "P6"), "P6", 2),
            (("M4", "M5", "M6"), "M6", 2),
            (("P3", "P4", "P5"), "P3", 0),
            (("M5", "M6", "M7"), "M6", 1),
            (("P7", "P8", "P9"), "P8", 1),
            (("P4", "P5", "P6"), "P5", 1),
            (("S2", "S3", "S4"), "S2", 0),
        )
        for index, (ids, incoming, shadow) in enumerate(shapes):
            with self.subTest(shape=index):
                d, m, frames = bundle(
                    ids, incoming, shadow,
                    discard_at=100 + index * 90,
                    meld_at=120 + index * 90,
                    shade_at=126 + index * 90,
                )
                out = cross_check_reviewed_meld_event(d, m, frames)
                self.assertEqual(
                    out.status, "DEVELOPMENT_CORROBORATED_CANDIDATE"
                )
                self.assertEqual(out.candidate_action_kind, "CHI_LIKE")
                self.assertEqual(out.reviewed_incoming_tile_candidate, incoming)
                self.assertEqual(out.shaded_face_index, shadow)
                self.assertEqual(out.shade_first_stable_frame,
                                 frames[6].frame_index)
                payload = out.to_dict()
                self.assertEqual(
                    payload["possible_action_interval_frames"],
                    [d.frame_index, m.frame_index],
                )
                self.assertEqual(payload["production_action_kind"], "UNKNOWN")
                self.assertEqual(
                    payload["production_incoming_tile_id"], "UNKNOWN"
                )
                self.assertFalse(payload["owner_confirmed_event_truth"])
                self.assertFalse(payload["independent_blind_test"])
                self.assertFalse(payload["formal_promotion_evidence"])
                self.assertFalse(payload["safe_for_runtime"])
                self.assertFalse(payload["safe_for_executor"])
                self.assertIsNone(payload["exact_action_frame"])

    def test_synthetic_peng_is_only_like_without_real_evidence(self):
        d, m, frames = bundle(
            ids=("W", "W", "W"), claimed="W", shade_index=1
        )
        result = cross_check_reviewed_meld_event(d, m, frames)
        self.assertEqual(result.candidate_action_kind, "PENG_LIKE")
        self.assertEqual(result.to_dict()["production_action_kind"], "UNKNOWN")

    def test_four_face_or_mixed_invalid_shape_abstains(self):
        for ids in (
            ("P4", "P5", "P6", "P7"),
            ("P4", "P5", "P8"),
            ("P4", "M5", "P6"),
            ("E", "N", "W"),
            ("P4", "UNKNOWN", "P6"),
            ("W", "W"),
        ):
            with self.subTest(ids=ids):
                d, m, frames = bundle(ids=ids)
                out = cross_check_reviewed_meld_event(d, m, frames)
                self.assertEqual(out.status, "UNKNOWN")
                self.assertEqual(out.candidate_action_kind, "UNKNOWN")

    def test_shaded_slot_not_matching_independently_reviewed_discard_conflicts(self):
        d, m, frames = bundle()
        d = replace(d, visible_tile_id="P5")
        result = cross_check_reviewed_meld_event(d, m, frames)
        self.assertEqual(result.status, "CONFLICT")
        self.assertIn("shaded_face_conflict", result.issues[0])
        self.assertIsNone(result.reviewed_incoming_tile_candidate)

    def test_fake_sha_session_epoch_are_rejected(self):
        d, m, frames = bundle()
        for tamper in (
            {"source_session": "other_original"},
            {"source_sha256": "b" * 64},
            {"stream_epoch": 2},
        ):
            with self.subTest(tamper=tamper):
                result = cross_check_reviewed_meld_event(
                    d, replace(m, **tamper), frames
                )
                self.assertEqual(result.status, "CONFLICT")
        bad_frames = [*frames]
        bad_frames[4] = replace(
            bad_frames[4], source_sha256="b" * 64
        )
        self.assertEqual(
            cross_check_reviewed_meld_event(d, m, bad_frames).status,
            "UNKNOWN",
        )

    def test_source_or_review_truth_unverified_must_abstain(self):
        d, m, frames = bundle()
        for field in (
            "original_video_sha_verified",
            "source_frame_pixel_verified",
            "explicit_tile_manually_reviewed",
            "no_intervening_public_action_reviewed",
        ):
            with self.subTest(which=field):
                result = cross_check_reviewed_meld_event(
                    replace(d, **{field: False}), m, frames
                )
                self.assertEqual(result.status, "UNKNOWN")
        for field in (
            "original_video_sha_verified",
            "source_frame_pixel_verified",
            "user_approved_face_id_provenance",
            "independently_reviewed_absent_before_present",
        ):
            with self.subTest(which=field):
                result = cross_check_reviewed_meld_event(
                    d, replace(m, **{field: False}), frames
                )
                self.assertEqual(result.status, "UNKNOWN")

    def test_preexisting_group_later_darkening_is_not_a_second_action(self):
        d, m, frames = bundle(
            ids=("S2", "S3", "S4"), claimed="S2", shade_index=0,
            discard_at=50, meld_at=100, shade_at=190,
        )
        # No independently reviewed ABSENT-before-present transition.
        already_exposed = replace(
            m, independently_reviewed_absent_before_present=False
        )
        out = cross_check_reviewed_meld_event(
            d, already_exposed, frames
        )
        self.assertEqual(out.status, "UNKNOWN")
        self.assertIsNone(out.shade_first_stable_frame)
        self.assertEqual(out.to_dict()["production_action_kind"], "UNKNOWN")

    def test_left_censored_shade_or_one_frame_flash_abstains(self):
        d, m, frames = bundle()
        all_shaded = [
            replace(f, shadow_index=2) for f in frames
        ]
        self.assertEqual(
            cross_check_reviewed_meld_event(d, m, all_shaded).status,
            "UNKNOWN",
        )
        flash = [
            replace(f, shadow_index=2 if i == 6 else None)
            for i, f in enumerate(frames)
        ]
        self.assertEqual(
            cross_check_reviewed_meld_event(d, m, flash).status,
            "UNKNOWN",
        )

    def test_missing_frames_and_intermittent_source_track_abstain(self):
        d, m, frames = bundle()
        for case in (
            frames[1:],
            frames[:3] + frames[4:],
            frames[:3] + [
                replace(f, meld_track_id="other_group")
                for f in frames[3:]
            ],
            frames[:3] + [
                replace(f, exact_source_frame_verified=False)
                for f in frames[3:]
            ],
            [],
        ):
            with self.subTest(case=len(case)):
                out = cross_check_reviewed_meld_event(d, m, case)
                self.assertEqual(out.status, "UNKNOWN")

    def test_same_side_or_reversed_timeline_never_attributes_actor(self):
        d, m, frames = bundle()
        self.assertEqual(
            cross_check_reviewed_meld_event(
                d, replace(m, screen_side="upper"), frames
            ).status, "UNKNOWN"
        )
        self.assertEqual(
            cross_check_reviewed_meld_event(
                replace(d, frame_index=m.frame_index), m, frames
            ).status, "UNKNOWN"
        )

    def test_delayed_shade_can_arrive_many_frames_after_group(self):
        d, m, frames = bundle(
            ids=("S2", "S3", "S4"), claimed="S2", shade_index=0,
            discard_at=50, meld_at=100, shade_at=220,
        )
        result = cross_check_reviewed_meld_event(
            d, m, frames, verified_fps=30.0
        )
        self.assertEqual(
            result.status, "DEVELOPMENT_CORROBORATED_CANDIDATE"
        )
        self.assertEqual(result.appearance_delay_frames, 120)
        self.assertEqual(result.shade_first_stable_frame, 220)
        self.assertIsNone(result.to_dict()["actual_action_to_shade_delay"])

    def test_competing_stable_shade_positions_fail_closed(self):
        d, m, frames = bundle(shade_at=130)
        frames = [
            replace(f, shadow_index=(1 if f.frame_index >= 133
                                    else f.shadow_index))
            for f in frames
        ]
        out = cross_check_reviewed_meld_event(d, m, frames)
        self.assertEqual(out.status, "UNKNOWN")
        self.assertEqual(out.to_dict()["production_action_kind"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
