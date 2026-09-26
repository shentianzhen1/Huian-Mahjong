"""Synthetic #69 interface contracts across independent hand, multi-signal and replay scoring.

No original video, hashes, player metadata, runtime promotion or executor.
"""
import unittest

from workspace.vision.public_independent_hand_count import (
    HandCountFrame, review_independent_hand_count,
)
from workspace.vision.public_dual_region_transition import DualRegionSourceReview
from workspace.vision.public_multi_signal_review import review_multi_signal_window
from workspace.vision.original_replay_metrics import score_replay

_SYNTHETIC_SHA = "0" * 64


def hand_frames(*, trusted=True, session="synthetic_session"):
    return [
        HandCountFrame(
            session=session, source_sha256=_SYNTHETIC_SHA, epoch=0,
            frame=i, screen_side="lower", count=10 if i < 3 else 8,
            source_pixels_verified=True, independent_hand_roi_verified=trusted,
            unobscured=True, animation_free=True,
            draw_region_separately_counted=True,
        )
        for i in range(6)
    ]


class Issue69IntegrationContractTests(unittest.TestCase):
    def test_hand_delta_never_becomes_an_action(self):
        hand = review_independent_hand_count(hand_frames(), transition_after_frame=3)
        self.assertEqual(hand.delta, -2)
        public = hand.to_dict()
        self.assertEqual(public["action_kind"], "UNKNOWN")
        self.assertFalse(public["safe_for_runtime"])
        self.assertFalse(public["safe_for_executor"])

    def test_unverified_hand_roi_abstains_through_multi_signal(self):
        hand = review_independent_hand_count(
            hand_frames(trusted=False), transition_after_frame=3)
        self.assertEqual(hand.status, "UNKNOWN")
        dual = DualRegionSourceReview(
            "SYNCHRONIZED_TWO_REGION_APPEARANCE_CANDIDATE_ONLY",
            "synthetic_only", prior_frame=2, first_visible_frame=3,
        )
        combined = review_multi_signal_window(
            dual, hand, None,
            same_original_source_epoch_independently_verified=True,
            hand_roi_distinct_from_lower_meld_roi=True,
            wall_roi_distinct_from_both=True,
            explicit_review_window=(2, 3),
        )
        self.assertEqual(combined.status, "UNKNOWN")
        self.assertEqual(combined.reason, "independent_hand_count_transition_missing")

    def test_candidate_requires_independent_source_attestation(self):
        hand = review_independent_hand_count(hand_frames(), transition_after_frame=3)
        dual = DualRegionSourceReview(
            "SYNCHRONIZED_TWO_REGION_APPEARANCE_CANDIDATE_ONLY",
            "synthetic_only", prior_frame=2, first_visible_frame=3,
        )
        args = dict(
            dual=dual, hand=hand, wall=None,
            hand_roi_distinct_from_lower_meld_roi=True,
            wall_roi_distinct_from_both=True,
            explicit_review_window=(2, 3),
        )
        refused = review_multi_signal_window(
            **args, same_original_source_epoch_independently_verified=False)
        self.assertEqual(refused.status, "UNKNOWN")
        candidate = review_multi_signal_window(
            **args, same_original_source_epoch_independently_verified=True)
        self.assertEqual(candidate.status, "MULTI_SIGNAL_OWNER_REVIEW_CANDIDATE_ONLY")
        self.assertEqual(candidate.hand_delta, -2)
        self.assertEqual(candidate.to_dict()["action_kind"], "UNKNOWN")
        self.assertFalse(candidate.to_dict()["verified_real_video_event"])
        self.assertFalse(candidate.to_dict()["safe_for_executor"])

    def test_development_candidate_cannot_be_counted_as_prediction(self):
        hand = review_independent_hand_count(hand_frames(), transition_after_frame=3)
        dual = DualRegionSourceReview(
            "SYNCHRONIZED_TWO_REGION_APPEARANCE_CANDIDATE_ONLY",
            "synthetic_only", prior_frame=2, first_visible_frame=3,
        )
        candidate = review_multi_signal_window(
            dual, hand, None,
            same_original_source_epoch_independently_verified=True,
            hand_roi_distinct_from_lower_meld_roi=True,
            wall_roi_distinct_from_both=True,
            explicit_review_window=(2, 3),
        )
        self.assertEqual(candidate.to_dict()["action_kind"], "UNKNOWN")
        result = score_replay({
            "video_id": "SYNTHETIC_NOT_ORIGINAL_VIDEO",
            "fps": 30, "duration_frames": 90,
            "ground_truth": [{"frame": 3, "kind": "CHI", "actor": "SELF"}],
            "predictions": [
                {"frame": 3, "kind": candidate.to_dict()["action_kind"],
                 "actor": candidate.to_dict()["actor"]},
            ],
        })
        self.assertEqual(result["known_machine_predictions"], 0)
        self.assertEqual(result["abstained_predictions"], 1)
        self.assertEqual(result["meld_detection"]["fn"], 1)
        self.assertIsNone(result["complete_action_reconstruction"])
        self.assertFalse(result["formal_source_disjoint_claim"])


if __name__ == "__main__":
    unittest.main()
