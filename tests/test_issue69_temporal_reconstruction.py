import unittest

from workspace.vision.issue69_public_replay_orchestrator import PublicReplayCandidate
from workspace.vision.public_claim_hand_count_delta import SourceScopedStableHandCount, review_new_meld_hand_count_delta
from workspace.vision.public_hand_count_fact_adapter import hand_count_review_to_source_fact
from workspace.vision.public_hand_identity_delta import StableHandIdentitySnapshot, review_hand_identity_delta
from workspace.vision.public_hand_identity_fact_adapter import identity_delta_to_hand_fact
from workspace.vision.issue69_temporal_reconstruction import (
    HandDeltaCandidate,
    reconstruct_public_candidates,
)

SHA = "a" * 64
SESSION = "hand1"


def public(channel, ts, frame, actor, kind, ref, tile=None, *, tiles=(),
           meld_group_size=None, previous_meld=(),
           previous_meld_group_size=None):
    return PublicReplayCandidate(
        channel=channel, timestamp_seconds=ts, frame_index=frame,
        actor_hint=actor, kind=kind, source_session=SESSION,
        source_sha256=SHA, stream_epoch=0, evidence_refs=(ref,), tile=tile,
        tiles=tiles, meld_group_size=meld_group_size,
        previous_meld=previous_meld,
        previous_meld_group_size=previous_meld_group_size,
    )


class Issue69TemporalReconstructionTests(unittest.TestCase):
    def test_three_independent_facts_reconstruct_ming_gang(self):
        rows = [
            public("river", 47.0, 100, "opponent", "DISCARD", "river:p6", "P6"),
            public("action_area", 47.1, 101, "player", "ACTION_AREA_ONSET", "ui:kong"),
            public("meld", 47.5, 105, "player", "MELD_DELTA", "meld:p6", "P6,P6,P6,P6"),
        ]
        hand = HandDeltaCandidate(
            timestamp_seconds=47.4, frame_index=104, actor="player",
            source_session=SESSION, source_sha256=SHA, stream_epoch=0,
            evidence_refs=("hand:removed3",), removed_tiles=("P6", "P6", "P6"),
        )
        report = reconstruct_public_candidates(
            rows, hand_deltas=[hand], claim_window_seconds=1.0,
            assembly_delay_seconds=0.0,
        )
        kinds = [row["kind"] for row in report["actions"]]
        self.assertIn("MING_GANG", kinds)
        gang = next(row for row in report["actions"] if row["kind"] == "MING_GANG")
        self.assertEqual(gang["claimed_tile"], "P6")
        self.assertEqual(gang["meld"], ["P6"] * 4)
        self.assertEqual(gang["evidence_grade"], "CORROBORATED")
        self.assertEqual(len(report["excluded_context"]), 1)
        self.assertEqual(
            report["excluded_context"][0]["reason"],
            "action_area_context_never_action_evidence",
        )
        self.assertFalse(report["safe_for_runtime"])
        self.assertFalse(report["safe_for_hint"])
        self.assertFalse(report["safe_for_executor"])

    def test_missing_hand_delta_expires_to_unknown_action(self):
        rows = [
            public("river", 47.0, 100, "opponent", "DISCARD", "river:p6", "P6"),
            public("meld", 47.5, 105, "player", "MELD_DELTA", "meld:p6", "P6,P6,P6,P6"),
        ]
        report = reconstruct_public_candidates(
            rows, claim_window_seconds=1.0, assembly_delay_seconds=0.0,
        )
        unknown = [row for row in report["actions"] if row["kind"] == "UNKNOWN_ACTION"]
        self.assertEqual(len(unknown), 1)
        self.assertIn(
            "meld_window_expired_without_unique_reconstruction",
            unknown[0]["unknown_reasons"],
        )
        self.assertEqual(unknown[0]["evidence_grade"], "UNKNOWN")

    def test_verified_semantic_count_fact_flows_into_assembler(self):
        def sample(frame, count, ref):
            return SourceScopedStableHandCount(
                source_session=SESSION, source_sha256=SHA, stream_epoch=0,
                frame_index=frame, actor="player", semantic_concealed_count=count,
                tracker_state="STABLE_HAND", tracker_trusted=True,
                tracker_stable=True, hand_geometry_region_verified=True,
                source_frame_verified=True, evidence_ref=ref,
            )
        before, after = sample(100, 16, "hand:before"), sample(102, 13, "hand:after")
        review = review_new_meld_hand_count_delta(
            before, after, new_meld_first_visible_frame=101,
            new_meld_face_count=4, pre_sample_brackets_onset=True,
            post_sample_before_followup_discard=True,
            independent_public_meld_onset_verified=True,
        )
        fact = hand_count_review_to_source_fact(
            before, after, review, timestamp_seconds=47.4,
        )
        self.assertIsNotNone(fact)
        rows = [
            public("river", 47.0, 90, "opponent", "DISCARD", "river:p6", "P6"),
            public("meld", 47.5, 105, "player", "MELD_DELTA", "meld:p6", "P6,P6,P6,P6"),
        ]
        report = reconstruct_public_candidates(
            rows, hand_facts=[fact], claim_window_seconds=1.0,
            assembly_delay_seconds=0.0,
        )
        gang = next(row for row in report["actions"] if row["kind"] == "MING_GANG")
        self.assertEqual(gang["claimed_tile"], "P6")
        self.assertEqual(gang["meld"], ["P6"] * 4)
        self.assertEqual(gang["evidence_grade"], "CORROBORATED")
        self.assertEqual(report["input_observation_count"], 3)

    def test_identity_qualified_hand_fact_closes_ming_gang(self):
        def count_sample(frame, count, ref):
            return SourceScopedStableHandCount(
                SESSION, SHA, 0, frame, "player", count, "STABLE_HAND",
                True, True, True, True, evidence_ref=ref,
            )
        cb, ca = count_sample(100, 16, "cb"), count_sample(102, 13, "ca")
        cr = review_new_meld_hand_count_delta(
            cb, ca, new_meld_first_visible_frame=101, new_meld_face_count=4,
            pre_sample_brackets_onset=True, post_sample_before_followup_discard=True,
            independent_public_meld_onset_verified=True,
        )
        before = StableHandIdentitySnapshot(
            SESSION, SHA, 0, 100, "player", ("P6","P6","P6","M1"),
            .90, .82, True, True, True, True, "identity:before",
        )
        after = StableHandIdentitySnapshot(
            SESSION, SHA, 0, 102, "player", ("M1",),
            .91, .82, True, True, True, True, "identity:after",
        )
        delta = review_hand_identity_delta(before, after, cr)
        fact = identity_delta_to_hand_fact(before, after, delta, timestamp_seconds=47.4)
        rows = [
            public("river", 47.0, 90, "opponent", "DISCARD", "river:p6", "P6"),
            public("meld", 47.5, 105, "player", "MELD_DELTA", "meld:p6", "P6,P6,P6,P6"),
        ]
        report = reconstruct_public_candidates(
            rows, hand_facts=[fact], claim_window_seconds=1.0,
            assembly_delay_seconds=0.0,
        )
        gang = next(row for row in report["actions"] if row["kind"] == "MING_GANG")
        self.assertEqual(gang["claimed_tile"], "P6")
        self.assertEqual(gang["meld"], ["P6"] * 4)
        self.assertEqual(gang["evidence_grade"], "CORROBORATED")

    def test_cross_source_hand_evidence_is_rejected(self):
        rows = [public("meld", 2, 20, "player", "MELD_DELTA", "m", "S1,S2,S3")]
        hand = HandDeltaCandidate(
            1.9, 19, "player", SESSION, "b" * 64, 0, ("h",),
            removed_tiles=("S1", "S3"),
        )
        with self.assertRaisesRegex(ValueError, "exact source scope"):
            reconstruct_public_candidates(
                rows, hand_deltas=[hand], claim_window_seconds=1,
                assembly_delay_seconds=0,
            )

    def test_replay_metadata_closes_exact_identity_add_kong(self):
        rows = [public(
            "meld", 112.1, 3363, "player", "MELD_DELTA", "meld:add-kong",
            tiles=("S8",) * 4, meld_group_size=4,
            previous_meld=("S8",) * 3, previous_meld_group_size=3,
        )]
        hand = HandDeltaCandidate(
            112.0, 3360, "player", SESSION, SHA, 0, ("hand:removed1",),
            removed_tiles=("S8",),
        )
        report = reconstruct_public_candidates(
            rows, hand_deltas=[hand], claim_window_seconds=1.0,
            assembly_delay_seconds=0.0,
        )
        add_kong = next(row for row in report["actions"] if row["kind"] == "ADD_KONG")
        self.assertEqual(add_kong["tile"], "S8")
        self.assertEqual(add_kong["meld"], ["S8"] * 4)
        self.assertEqual(add_kong["evidence_grade"], "CORROBORATED")

    def test_unknown_identity_three_to_four_stays_unknown(self):
        rows = [public(
            "meld", 112.1, 3363, "player", "MELD_DELTA",
            "meld:add-kong-unknown", tiles=(None, None, None, None),
            meld_group_size=4, previous_meld=(), previous_meld_group_size=3,
        )]
        hand = HandDeltaCandidate(
            112.0, 3360, "player", SESSION, SHA, 0, ("hand:removed1",),
            removed_count=1,
        )
        report = reconstruct_public_candidates(
            rows, hand_deltas=[hand], claim_window_seconds=1.0,
            assembly_delay_seconds=0.0,
        )
        self.assertFalse(any(row["kind"] == "ADD_KONG" for row in report["actions"]))
        self.assertTrue(any(row["kind"] == "UNKNOWN_ACTION" for row in report["actions"]))
        self.assertEqual(len(report["meld_upgrade_candidates"]), 1)
        upgrade = report["meld_upgrade_candidates"][0]
        self.assertEqual(upgrade["previous_group_size"], 3)
        self.assertEqual(upgrade["current_group_size"], 4)
        self.assertFalse(upgrade["tile_identity_complete"])
        self.assertEqual(upgrade["action_kind"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
