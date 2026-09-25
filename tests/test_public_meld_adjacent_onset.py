"""Synthetic source-scoped consecutive-frame onset verification for #69.

Private videos are excluded from CI. The asserted source review fields below
test only gate behavior and are NOT proof of accurate upstream segmentation.
"""
from __future__ import annotations

from dataclasses import replace
import unittest

from workspace.vision.public_meld_adjacent_onset import (
    AdjacentPublicMeldSourceFrame,
    ObservedPublicMeldTrack,
    review_adjacent_public_meld_onset,
)

SHA = "a" * 64
OLD = ObservedPublicMeldTrack("already_exposed", ("P1", "P2", "P3"))
NEW = ObservedPublicMeldTrack("candidate_g", ("M4", "M5", "M6"))


def frame(index, tracks=(), **changes):
    kwargs = dict(
        source_session="synthetic_original_video",
        source_sha256=SHA,
        decoded_frame_sha256=("b" if index == 122 else "c") * 64,
        stream_epoch=2,
        frame_index=index,
        screen_side="lower",
        frame_size=(1046, 480),
        public_meld_tracks=tracks,
        original_video_sha_verified=True,
        original_frame_pixels_verified=True,
        public_meld_region_separated_from_hand_gold=True,
        explicit_source_public_meld_region_verified=True,
        is_unobscured_source_frame=True,
    )
    kwargs.update(changes)
    return AdjacentPublicMeldSourceFrame(**kwargs)


def check(before=None, after=None, *, target=NEW):
    return review_adjacent_public_meld_onset(
        before or frame(122, (OLD,)),
        after or frame(123, (OLD, target)),
        target_track_id=target.track_id,
        approved_target_face_ids=target.face_ids,
    )


class AdjacentOnsetTests(unittest.TestCase):
    def test_one_new_regular_public_group_is_adjacent_only_review_candidate(self):
        out = check()
        self.assertEqual(out.status, "NEW_MELD_VISUALLY_BRACKETED_OWNER_ACTION_PENDING")
        self.assertEqual((out.prior_frame, out.first_visible_frame), (122, 123))
        self.assertEqual(out.target_face_ids, ("M4", "M5", "M6"))
        self.assertEqual(out.screen_side, "lower")
        p = out.to_dict()
        self.assertEqual(p["original_adjacent_frame_delta"], 1)
        self.assertEqual(p["action_kind"], "UNKNOWN")
        self.assertEqual(p["incoming_tile_id"], "UNKNOWN")
        self.assertFalse(p["hand_shadow_used"])
        self.assertFalse(p["late_shade_used_as_action_timestamp"])
        self.assertFalse(p["owner_confirmed_action"])
        self.assertFalse(p["safe_for_runtime"])
        self.assertFalse(p["safe_for_executor"])
        self.assertNotIn(SHA, str(p))
        self.assertNotIn("synthetic_original_video", str(p))

    def test_existing_group_mere_later_shade_is_not_new_action(self):
        out = check(before=frame(122, (OLD, NEW)))
        self.assertEqual(out.status, "PREEXISTING_MELD_NO_NEW_ACTION")
        self.assertEqual(out.to_dict()["action_kind"], "UNKNOWN")

    def test_existing_group_retracked_under_new_id_abstains(self):
        reid = ObservedPublicMeldTrack("old_g_different_id", NEW.face_ids)
        out = check(before=frame(122, (OLD, reid)))
        self.assertEqual(out.status, "UNKNOWN")
        self.assertIn("preexisted", out.reason)

    def test_hand_or_gold_not_a_verified_public_meld_roi(self):
        for key in (
            "public_meld_region_separated_from_hand_gold",
            "explicit_source_public_meld_region_verified",
        ):
            with self.subTest(key=key):
                self.assertEqual(
                    check(before=frame(122, (OLD,), **{key: False})).status,
                    "UNKNOWN",
                )
                self.assertEqual(
                    check(after=frame(123, (OLD, NEW), **{key: False})).status,
                    "UNKNOWN",
                )

    def test_exact_decoded_original_pixels_and_provenance_required(self):
        for key in (
            "original_video_sha_verified",
            "original_frame_pixels_verified",
            "is_unobscured_source_frame",
        ):
            with self.subTest(key=key):
                self.assertEqual(
                    check(after=frame(123, (OLD, NEW), **{key: False})).status,
                    "UNKNOWN",
                )
        self.assertEqual(check(after=frame(
            123, (OLD, NEW), decoded_frame_sha256="b" * 64,
        )).status, "UNKNOWN")

    def test_different_source_session_sha_epoch_side_and_frame_size_rejected(self):
        for key, value in (
            ("source_session", "second_original_match"),
            ("source_sha256", "d" * 64),
            ("stream_epoch", 3),
            ("screen_side", "upper"),
            ("frame_size", (960, 448)),
        ):
            with self.subTest(key=key):
                self.assertEqual(
                    check(after=frame(123, (OLD, NEW), **{key: value})).status,
                    "UNKNOWN",
                )

    def test_exactly_adjacent_not_same_frame_or_sampled_gap(self):
        for index in (122, 124, 125, 121):
            with self.subTest(index=index):
                self.assertEqual(
                    check(after=frame(index, (OLD, NEW))).status, "UNKNOWN"
                )

    def test_known_prior_groups_must_remain_visible(self):
        self.assertEqual(check(after=frame(123, (NEW,))).status, "UNKNOWN")
        changed = ObservedPublicMeldTrack("already_exposed", ("P2", "P3", "P4"))
        self.assertEqual(
            check(after=frame(123, (changed, NEW))).status, "UNKNOWN",
        )

    def test_multiple_new_groups_are_ambiguous(self):
        extra = ObservedPublicMeldTrack("other_new", ("E", "E", "E"))
        self.assertEqual(
            check(after=frame(123, (OLD, NEW, extra))).status, "UNKNOWN",
        )

    def test_meld_target_must_match_approved_group_and_not_a_hand_tile(self):
        self.assertEqual(
            check(after=frame(123, (OLD, NEW)),
                  target=ObservedPublicMeldTrack("other", NEW.face_ids)).status,
            "UNKNOWN",
        )
        self.assertEqual(
            review_adjacent_public_meld_onset(
                frame(122, (OLD,)), frame(123, (OLD, NEW)),
                target_track_id=NEW.track_id,
                approved_target_face_ids=("M4", "M5", "M9"),
            ).status,
            "UNKNOWN",
        )

    def test_identical_peng_and_kong_need_no_shade(self):
        for ids in (("W", "W", "W"), ("P7",) * 4):
            with self.subTest(ids=ids):
                t = ObservedPublicMeldTrack("new_group", ids)
                self.assertEqual(
                    check(after=frame(123, (OLD, t)), target=t).status,
                    "NEW_MELD_VISUALLY_BRACKETED_OWNER_ACTION_PENDING",
                )

    def test_bad_source_or_duplicate_track_ids_abstain(self):
        for key, value in (
            ("source_sha256", "broken"),
            ("decoded_frame_sha256", "broken"),
            ("stream_epoch", True),
            ("frame_index", True),
            ("frame_size", (1046, 0)),
            ("screen_side", "unset"),
            ("source_session", ""),
        ):
            with self.subTest(key=key):
                self.assertEqual(
                    check(after=frame(123, (OLD, NEW), **{key: value})).status,
                    "UNKNOWN",
                )
        self.assertEqual(
            check(after=frame(123, (OLD, NEW, NEW))).status,
            "UNKNOWN",
        )

    def test_invalid_meld_track_rejected_at_construction(self):
        for identity in ((), ("M1",), ("M1", "UNKNOWN", "M3"),
                         ("P1", "P2", "P3", "P4", "P5")):
            with self.subTest(identity=identity):
                with self.assertRaises(ValueError):
                    ObservedPublicMeldTrack("bad", identity)

    def test_unapproved_requested_target_abstains(self):
        self.assertEqual(review_adjacent_public_meld_onset(
            frame(122, (OLD,)), frame(123, (OLD, NEW)),
            target_track_id="", approved_target_face_ids=NEW.face_ids,
        ).status, "UNKNOWN")
        self.assertEqual(review_adjacent_public_meld_onset(
            frame(122, (OLD,)), frame(123, (OLD, NEW)),
            target_track_id=NEW.track_id,
            approved_target_face_ids=("M1", "M1", "UNKNOWN"),
        ).status, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
