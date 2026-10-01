import unittest

from workspace.vision.issue69_public_replay_orchestrator import PublicReplayCandidate
from workspace.vision.issue69_temporal_reconstruction import (
    HandDeltaCandidate,
    reconstruct_public_candidates,
)

SHA = "a" * 64
SESSION = "hand1"


def public(channel, ts, frame, actor, kind, ref, tile=None):
    return PublicReplayCandidate(
        channel=channel, timestamp_seconds=ts, frame_index=frame,
        actor_hint=actor, kind=kind, source_session=SESSION,
        source_sha256=SHA, stream_epoch=0, evidence_refs=(ref,), tile=tile,
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


if __name__ == "__main__":
    unittest.main()
