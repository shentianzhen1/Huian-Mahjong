"""#69: paired UPPER-withdrawal/LOWER-onset synthetic source controls.

These tests do not include or label private original-frame screenshots and
do not claim any independent automatic real-video match accuracy.
"""
from __future__ import annotations

from dataclasses import replace
import unittest

from workspace.vision.public_dual_region_transition import (
    review_dual_region_original_frame_transition,
)
from workspace.vision.public_meld_adjacent_onset import AdjacentMeldOnsetReview
from workspace.vision.public_raised_tile_withdrawal import (
    RaisedPublicTileWithdrawal,
)

SOURCE = "a" * 64


def upper():
    return RaisedPublicTileWithdrawal(
        status="PUBLIC_RAISED_TILE_WITHDRAWAL_OPTICAL_CANDIDATE_ONLY",
        reason="synthetic_original_pixels",
        prior_frame=90,
        after_frame=91,
        prior_candidates=1,
        after_candidates=0,
        before_bbox=(450, 50, 125, 90),
        source_session="synthetic_original_one",
        source_sha256=SOURCE,
        stream_epoch=2,
    )


def lower():
    return AdjacentMeldOnsetReview(
        status="NEW_MELD_VISUALLY_BRACKETED_OWNER_ACTION_PENDING",
        reason="synthetic_independently_reviewed_lower",
        source_session="synthetic_original_one",
        source_sha256=SOURCE,
        stream_epoch=2,
        screen_side="lower",
        target_track_id="synthetic_new_lower_group",
        target_face_ids=("P4", "P5", "P6"),
        prior_frame=90,
        first_visible_frame=91,
    )


def check(up=None, lo=None, **changes):
    controls = dict(
        upper_stable_raised_precontrols_source_verified=True,
        upper_stable_absent_postcontrols_source_verified=True,
        upper_and_lower_roi_independently_reviewed=True,
    )
    controls.update(changes)
    return review_dual_region_original_frame_transition(
        up if up is not None else upper(),
        lo if lo is not None else lower(),
        **controls,
    )


class DualRegionOriginalFrameTests(unittest.TestCase):
    def test_two_independently_reviewed_regions_share_one_frame_pair(self):
        result = check()
        self.assertEqual(
            result.status,
            "SYNCHRONIZED_TWO_REGION_APPEARANCE_CANDIDATE_ONLY",
        )
        self.assertEqual((result.prior_frame, result.first_visible_frame),
                         (90, 91))
        data = result.to_dict()
        self.assertEqual(data["source_adjacent_frame_delta"], 1)
        self.assertEqual(data["actual_action_kind"], "UNKNOWN")
        self.assertEqual(data["claimed_discard_identity"], "UNKNOWN")
        self.assertEqual(data["hand_count_delta"], "UNKNOWN")
        self.assertFalse(data["independent_triple_observer_verified"])
        self.assertFalse(data["independent_full_automated_meld_detection"])
        self.assertFalse(data["safe_for_runtime"])
        self.assertFalse(data["safe_for_executor"])
        self.assertNotIn(SOURCE, str(data))
        self.assertNotIn("synthetic_original_one", str(data))

    def test_upper_only_ordinary_turn_cannot_be_published_as_claim(self):
        result = check(lo=replace(
            lower(), status="UNKNOWN", reason="no_new_lower_meld"
        ))
        self.assertEqual(result.status, "UNKNOWN")
        self.assertIn("no_separately_reviewed", result.reason)

    def test_no_upper_withdrawal_or_two_competing_upper_candidates(self):
        for up in (
            replace(upper(), status="UNKNOWN"),
            replace(upper(), prior_candidates=2),
            replace(upper(), after_candidates=1),
        ):
            with self.subTest(up=up):
                self.assertEqual(check(up=up).status, "UNKNOWN")

    def test_missing_or_invalid_source_provenance_refused(self):
        for field,value in (
            ("source_session", None),
            ("source_session", "another_match"),
            ("source_sha256", "b" * 64),
            ("stream_epoch", 3),
        ):
            with self.subTest(field=field,value=value):
                self.assertEqual(check(up=replace(upper(),**{field:value})).status,
                                 "UNKNOWN")

    def test_matching_frames_but_different_original_source_rejected(self):
        self.assertIn("source_or_epoch", check(
            lo=replace(lower(), source_sha256="b" * 64)).reason)

    def test_nonconsecutive_or_mismatched_frame_pairs_abstain(self):
        for up,lo in (
            (replace(upper(), after_frame=92), lower()),
            (upper(), replace(lower(), prior_frame=88)),
            (upper(), replace(lower(), first_visible_frame=94)),
        ):
            with self.subTest(before=up.prior_frame):
                x=check(up=up,lo=lo)
                self.assertEqual(x.status, "UNKNOWN")
                self.assertIn("same_adjacent", x.reason)

    def test_no_assumption_that_upper_and_lower_are_same_screen_side(self):
        self.assertEqual(check(lo=replace(lower(),screen_side="upper")).status,
                         "UNKNOWN")

    def test_source_control_frames_independently_required(self):
        for flag in (
            "upper_stable_raised_precontrols_source_verified",
            "upper_stable_absent_postcontrols_source_verified",
            "upper_and_lower_roi_independently_reviewed",
        ):
            with self.subTest(flag=flag):
                self.assertEqual(check(**{flag:False}).status,"UNKNOWN")

    def test_preexisting_group_with_delayed_shade_cannot_be_new_meld(self):
        stale=replace(lower(),status="PREEXISTING_MELD_NO_NEW_ACTION")
        self.assertEqual(check(lo=stale).status,"UNKNOWN")

    def test_four_identical_public_faces_still_do_not_establish_kong(self):
        lo=replace(lower(),target_face_ids=("M6",)*4)
        result=check(lo=lo)
        self.assertEqual(result.status,
                         "SYNCHRONIZED_TWO_REGION_APPEARANCE_CANDIDATE_ONLY")
        self.assertEqual(result.lower_face_count,4)
        self.assertEqual(result.to_dict()["actual_action_kind"],"UNKNOWN")

    def test_unknown_public_face_track_or_no_bbox_rejected(self):
        self.assertEqual(check(lo=replace(lower(),target_track_id="")).status,
                         "UNKNOWN")
        self.assertEqual(check(up=replace(upper(),before_bbox=None)).status,
                         "UNKNOWN")

    def test_never_reuse_different_original_match_as_positive_example(self):
        a=replace(upper(),source_session="original_A")
        b=replace(lower(),source_session="original_B")
        self.assertEqual(check(up=a,lo=b).status,"UNKNOWN")


if __name__ == "__main__":
    unittest.main()
