"""Synthetic #69 independent-observer cross evidence; NO private images."""
from __future__ import annotations

from dataclasses import replace
import unittest

from workspace.vision.public_match_reconstruction import ObservationKind, RawObservation
from workspace.vision.public_meld_action_cross_evidence import (
    ManuallyReviewedNewMeld, ManuallyReviewedPublicDiscard,
)
from workspace.vision.public_meld_delayed_shade_review import SourceScopedShadeFrame
from workspace.vision.public_meld_observer_corroboration import (
    SourceBoundObserverFact, corroborate_with_independent_observers,
)

SHA = "a" * 64
SESSION = "synthetic_single_original"
SIDES = {"upper": "opponent", "lower": "player"}


def bundle(ids=("P4", "P5", "P6"), claimed="P6", shade_index=2):
    reviewed_discard = ManuallyReviewedPublicDiscard(
        source_session=SESSION, source_sha256=SHA, stream_epoch=3,
        frame_index=100, screen_side="upper", visible_tile_id=claimed,
        original_video_sha_verified=True, source_frame_pixel_verified=True,
        explicit_tile_manually_reviewed=True,
        no_intervening_public_action_reviewed=True,
    )
    reviewed_meld = ManuallyReviewedNewMeld(
        source_session=SESSION, source_sha256=SHA, stream_epoch=3,
        meld_track_id="reviewed_lower_meld",
        frame_index=120, screen_side="lower",
        face_ids_left_to_right=ids,
        original_video_sha_verified=True, source_frame_pixel_verified=True,
        user_approved_face_id_provenance=True,
        independently_reviewed_absent_before_present=True,
    )
    shades = tuple(
        SourceScopedShadeFrame(
            source_session=SESSION, source_sha256=SHA,
            stream_epoch=3, meld_track_id="reviewed_lower_meld",
            frame_index=i,
            shadow_index=shade_index if i >= 124 else None,
            reviewed_public_meld=True,
            regular_three_faces=True,
            exact_source_frame_verified=True,
        )
        for i in range(120, 127)
    ) if len(ids) == 3 and len(set(ids)) == 3 else ()

    discarded = RawObservation(
        4.0, "opponent", ObservationKind.DISCARD, tile=claimed,
        confidence=.9, evidence_refs=("independent-river-frame:101",),
    )
    hand = RawObservation(
        4.2, "player", ObservationKind.HAND_DELTA,
        confidence=.9, evidence_refs=("independent-hand-frame:122",),
        details={"removed_tiles": list(remove_one(ids, claimed))},
    )
    meld = RawObservation(
        4.3, "player", ObservationKind.MELD_DELTA, tiles=ids,
        confidence=.9, evidence_refs=("independent-meld-frame:123",),
    )
    def fact(channel, obs, frame):
        return SourceBoundObserverFact(
            channel=channel, observation=obs,
            source_session=SESSION, source_sha256=SHA,
            stream_epoch=3, frame_index=frame,
            original_frame_verified=True, stable_source_observation=True,
            independent_public_region_verified=True,
        )
    return (
        reviewed_discard, reviewed_meld, shades,
        fact("river", discarded, 101),
        fact("hand", hand, 122),
        fact("meld", meld, 123),
    )


def remove_one(ids, claimed):
    remaining = list(ids)
    remaining.remove(claimed)
    return tuple(remaining)


def gate(parts, **kwargs):
    opts = {"verified_screen_side_actors": SIDES, "reviewed_last_frame": 126}
    opts.update(kwargs)
    return corroborate_with_independent_observers(*parts, **opts)


class IndependentObserverCorroborationTests(unittest.TestCase):
    def test_three_distinct_observer_channels_agree_on_synthetic_chi(self):
        result = gate(bundle())
        self.assertEqual(
            result.status, "OBSERVER_CORROBORATED_OWNER_REVIEW_PENDING"
        )
        self.assertEqual(result.candidate_action_kind, "CHI_LIKE")
        self.assertEqual(result.candidate_incoming_tile, "P6")
        self.assertEqual(result.observer_evidence_grade, "CORROBORATED")
        self.assertEqual(result.observation_frames, (101, 122, 123))
        payload = result.to_dict()
        self.assertEqual(payload["reviewed_window_frames"], [100, 120])
        self.assertFalse(payload["owner_confirmed_event_truth"])
        self.assertFalse(payload["source_disjoint_blind_test"])
        self.assertFalse(payload["safe_for_runtime"])
        self.assertFalse(payload["safe_for_executor"])
        self.assertEqual(payload["production_action_kind"], "UNKNOWN")
        self.assertEqual(payload["production_incoming_tile_id"], "UNKNOWN")
        self.assertNotIn(SHA, str(payload))
        self.assertNotIn(SESSION, str(payload))

    def test_identical_peng_and_ming_kong_require_no_shade(self):
        for ids, claimed, kind in (
            (("W", "W", "W"), "W", "PENG_LIKE"),
            (("P7", "P7", "P7", "P7"), "P7", "KONG_LIKE"),
        ):
            with self.subTest(kind=kind):
                parts = bundle(ids, claimed)
                self.assertEqual(parts[2], ())
                result = gate(parts)
                self.assertEqual(
                    result.status, "OBSERVER_CORROBORATED_OWNER_REVIEW_PENDING"
                )
                self.assertEqual(result.candidate_action_kind, kind)
                self.assertEqual(result.candidate_incoming_tile, claimed)
                self.assertFalse(result.to_dict()["safe_for_runtime"])

    def test_chi_without_later_shade_abstains(self):
        parts = list(bundle())
        parts[2] = ()
        result = gate(parts)
        self.assertEqual(result.status, "UNKNOWN")

    def test_manual_face_review_not_claimed_event_truth(self):
        parts = list(bundle())
        parts[1] = replace(
            parts[1], independently_reviewed_absent_before_present=False,
        )
        self.assertEqual(gate(parts).status, "UNKNOWN")

    def test_observer_requires_original_sha_and_epoch(self):
        for alteration in (
            {"source_session": "other_match"},
            {"source_sha256": "b" * 64},
            {"stream_epoch": 4},
        ):
            with self.subTest(alteration=alteration):
                parts = list(bundle())
                parts[4] = replace(parts[4], **alteration)
                result = gate(parts)
                self.assertEqual(result.status, "CONFLICT")
                self.assertEqual(result.to_dict()["production_action_kind"], "UNKNOWN")

    def test_frame_pixel_stability_and_region_checks_fail_closed(self):
        for name in (
            "original_frame_verified",
            "stable_source_observation",
            "independent_public_region_verified",
        ):
            with self.subTest(name=name):
                parts = list(bundle())
                parts[5] = replace(parts[5], **{name: False})
                self.assertEqual(gate(parts).status, "UNKNOWN")

    def test_cannot_reuse_same_reference_as_two_independent_channels(self):
        parts = list(bundle())
        hand = parts[4].observation
        parts[4] = replace(
            parts[4],
            observation=replace(
                hand, evidence_refs=parts[3].observation.evidence_refs
            ),
        )
        result = gate(parts)
        self.assertEqual(result.status, "UNKNOWN")
        self.assertIn("share_or_lack_provenance", result.issues[0])

    def test_missing_evidence_reference_abstains(self):
        parts = list(bundle())
        parts[3] = replace(
            parts[3],
            observation=replace(
                parts[3].observation, evidence_refs=()
            ),
        )
        self.assertEqual(gate(parts).status, "UNKNOWN")

    def test_incorrect_actor_mapping_conflicts(self):
        parts = list(bundle())
        self.assertEqual(
            gate(parts, verified_screen_side_actors=None).status, "UNKNOWN"
        )
        inverted = {"upper": "player", "lower": "opponent"}
        self.assertEqual(
            gate(parts, verified_screen_side_actors=inverted).status,
            "CONFLICT",
        )

    def test_wrong_removed_tiles_do_not_pass_reconstruction(self):
        parts = list(bundle())
        hand = parts[4].observation
        parts[4] = replace(
            parts[4],
            observation=replace(
                hand, details={"removed_tiles": ["P3", "P4"]}
            ),
        )
        self.assertEqual(gate(parts).status, "CONFLICT")

    def test_opponent_hand_count_can_only_make_review_pending(self):
        parts = list(bundle())
        hand = parts[4].observation
        parts[4] = replace(
            parts[4],
            observation=replace(hand, details={"removed_count": 2}),
        )
        result = gate(parts)
        self.assertEqual(
            result.status, "OBSERVER_CORROBORATED_OWNER_REVIEW_PENDING"
        )
        self.assertFalse(result.to_dict()["owner_confirmed_event_truth"])
        self.assertFalse(result.to_dict()["safe_for_runtime"])

    def test_observer_discard_vs_manual_discard_conflict(self):
        parts = list(bundle())
        discard = parts[3].observation
        parts[3] = replace(
            parts[3], observation=replace(discard, tile="P5"),
        )
        self.assertEqual(gate(parts).status, "CONFLICT")

    def test_observer_group_shape_or_claim_mismatch_conflicts(self):
        parts = list(bundle())
        meld = parts[5].observation
        parts[5] = replace(
            parts[5], observation=replace(meld, tiles=("P5", "P5", "P5")),
        )
        self.assertEqual(gate(parts).status, "CONFLICT")

    def test_explicit_timeline_window_is_mandatory_not_hardcoded(self):
        parts = list(bundle())
        self.assertEqual(
            gate(parts, reviewed_last_frame=None).status, "UNKNOWN"
        )
        self.assertEqual(
            gate(parts, reviewed_last_frame=119).status, "UNKNOWN"
        )
        self.assertEqual(
            gate(parts, reviewed_last_frame=122).status, "UNKNOWN"
        )

    def test_wrong_source_frame_window_and_event_order_abstain(self):
        for index, new_frame in ((3, 99), (3, 121), (4, 99), (5, 127)):
            with self.subTest(index=index, frame=new_frame):
                parts = list(bundle())
                parts[index] = replace(parts[index], frame_index=new_frame)
                self.assertEqual(gate(parts).status, "UNKNOWN")

    def test_channel_type_and_bad_observation_kind_fail_closed(self):
        parts = list(bundle())
        parts[5] = replace(parts[5], channel="river")
        self.assertEqual(gate(parts).status, "UNKNOWN")
        parts = list(bundle())
        parts[4] = replace(
            parts[4],
            observation=replace(parts[4].observation, kind=ObservationKind.DISCARD),
        )
        self.assertEqual(gate(parts).status, "UNKNOWN")

    def test_unreviewed_peng_to_kong_upgrade_not_in_new_group_gate(self):
        parts = list(bundle(("W", "W", "W", "W"), "W"))
        parts[1] = replace(
            parts[1], independently_reviewed_absent_before_present=False,
        )
        self.assertEqual(gate(parts).status, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
