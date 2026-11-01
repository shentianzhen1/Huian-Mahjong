"""Synthetic bridge from semantic count review to source-bound HAND_DELTA."""
from __future__ import annotations

from dataclasses import replace
import unittest

from workspace.vision.public_claim_hand_count_delta import (
    SourceScopedStableHandCount,
    review_new_meld_hand_count_delta,
)
from workspace.vision.public_hand_count_fact_adapter import (
    hand_count_review_to_source_fact,
)
from workspace.vision.public_match_reconstruction import ObservationKind

SHA = "a" * 64


def sample(frame, count, **changes):
    values = dict(
        source_session="synthetic_original",
        source_sha256=SHA,
        stream_epoch=7,
        frame_index=frame,
        actor="player",
        semantic_concealed_count=count,
        tracker_state="STABLE_HAND",
        tracker_trusted=True,
        tracker_stable=True,
        hand_geometry_region_verified=True,
        source_frame_verified=True,
        draw_event_in_sample=False,
        discard_event_in_sample=False,
        hand_resort_or_occlusion_in_sample=False,
        geometry_baseline_reset_in_sample=False,
        evidence_ref=f"semantic-count:{frame}",
    )
    values.update(changes)
    return SourceScopedStableHandCount(**values)


def reviewed(before, after, faces=3):
    return review_new_meld_hand_count_delta(
        before, after,
        new_meld_first_visible_frame=before.frame_index + 1,
        new_meld_face_count=faces,
        pre_sample_brackets_onset=True,
        post_sample_before_followup_discard=True,
        independent_public_meld_onset_verified=True,
    )


class HandCountFactAdapterTests(unittest.TestCase):
    def test_successful_three_face_review_becomes_count_only_hand_delta(self):
        before, after = sample(100, 16), sample(102, 14)
        fact = hand_count_review_to_source_fact(
            before, after, reviewed(before, after, 3),
            timestamp_seconds=4.2,
        )
        self.assertIsNotNone(fact)
        self.assertEqual(fact.channel, "hand")
        self.assertEqual(fact.observation.kind, ObservationKind.HAND_DELTA)
        self.assertEqual(fact.observation.actor, "player")
        self.assertEqual(fact.observation.details["removed_count"], 2)
        self.assertFalse(fact.observation.details["hand_delta_identity_observed"])
        self.assertFalse(fact.observation.details["concealed_hand_shadow_used"])
        self.assertEqual(
            fact.observation.evidence_refs,
            ("semantic-count:100", "semantic-count:102"),
        )
        self.assertEqual(fact.frame_index, 102)

    def test_successful_four_face_new_group_becomes_removed_count_three(self):
        before, after = sample(200, 16), sample(203, 13)
        review = review_new_meld_hand_count_delta(
            before, after,
            new_meld_first_visible_frame=201,
            new_meld_face_count=4,
            pre_sample_brackets_onset=True,
            post_sample_before_followup_discard=True,
            independent_public_meld_onset_verified=True,
        )
        fact = hand_count_review_to_source_fact(
            before, after, review, timestamp_seconds=7.0,
        )
        self.assertIsNotNone(fact)
        self.assertEqual(fact.observation.details["removed_count"], 3)

    def test_conflict_or_unknown_review_never_becomes_fact(self):
        before, after = sample(100, 16), sample(102, 15)
        review = reviewed(before, after, 3)
        self.assertEqual(review.status, "CONFLICT")
        self.assertIsNone(hand_count_review_to_source_fact(
            before, after, review, timestamp_seconds=4.0,
        ))
        unknown = replace(review, status="UNKNOWN")
        self.assertIsNone(hand_count_review_to_source_fact(
            before, after, unknown, timestamp_seconds=4.0,
        ))

    def test_source_actor_and_reference_mismatch_fail_closed(self):
        before, after = sample(100, 16), sample(102, 14)
        review = reviewed(before, after)
        variants = (
            replace(after, source_session="other"),
            replace(after, source_sha256="b" * 64),
            replace(after, stream_epoch=8),
            replace(after, actor="opponent"),
            replace(after, evidence_ref=before.evidence_ref),
            replace(after, evidence_ref=""),
        )
        for changed in variants:
            with self.subTest(changed=changed):
                self.assertIsNone(hand_count_review_to_source_fact(
                    before, changed, review, timestamp_seconds=4.0,
                ))

    def test_review_fields_must_exactly_match_source_samples(self):
        before, after = sample(100, 16), sample(102, 14)
        review = reviewed(before, after)
        for patch in (
            {"actor": "opponent"},
            {"before_frame": 99},
            {"after_frame": 103},
            {"before_count": 15},
            {"after_count": 13},
            {"removed_count": 3},
            {"new_meld_face_count": 4},
        ):
            with self.subTest(patch=patch):
                self.assertIsNone(hand_count_review_to_source_fact(
                    before, after, replace(review, **patch),
                    timestamp_seconds=4.0,
                ))

    def test_invalid_timestamp_raises_instead_of_silent_cast(self):
        before, after = sample(100, 16), sample(102, 14)
        review = reviewed(before, after)
        for invalid in (True, -0.1, "4.0"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    hand_count_review_to_source_fact(
                        before, after, review, timestamp_seconds=invalid,
                    )


if __name__ == "__main__":
    unittest.main()
