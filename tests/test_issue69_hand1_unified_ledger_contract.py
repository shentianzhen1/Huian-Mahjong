"""Contract-only Hand 1 fixture for #69 unified replay ordering.

Times/actions are reviewed development fixtures, not machine accuracy evidence.
"""
import unittest

from workspace.vision.issue69_public_replay_orchestrator import (
    PublicReplayCandidate,
    assemble_public_replay_candidates,
)

SHA = "fba5f67d244fb5bdc916f24707de288fef939a9444fa66bec21347e52bd64fc3"
SESSION = "reviewed_match_2026_09_26_first_hand"


def candidate(channel, ts, frame, actor, kind, ref, tile=None):
    return PublicReplayCandidate(
        channel=channel,
        timestamp_seconds=ts,
        frame_index=frame,
        actor_hint=actor,
        kind=kind,
        source_session=SESSION,
        source_sha256=SHA,
        stream_epoch=0,
        evidence_refs=(ref,),
        tile=tile,
    )


class Issue69Hand1UnifiedLedgerContractTests(unittest.TestCase):
    def test_reviewed_sequence_can_share_one_fail_closed_ledger(self):
        report = assemble_public_replay_candidates([
            candidate("river", 47.0, 2780, "opponent", "DISCARD", "r:6p", "P6"),
            candidate("action_area", 47.2, 2792, "player", "ACTION_AREA_ONSET", "a:kong"),
            candidate("meld", 47.7, 2822, "player", "MELD_DELTA", "m:p6", "P6,P6,P6,P6"),
            candidate("river", 48.4, 2863, "player", "DISCARD", "r:m3", "M3"),
            candidate("river", 59.0, 3490, "opponent", "DISCARD", "r:p8", "P8"),
            candidate("river", 82.5, 4880, "player", "DISCARD", "r:s5", "S5"),
            candidate("action_area", 82.7, 4892, "opponent", "ACTION_AREA_ONSET", "a:s456"),
            candidate("meld", 83.2, 4922, "opponent", "MELD_DELTA", "m:s456", "S4,S5,S6"),
            candidate("river", 125.5, 7425, "player", "DISCARD", "r:s2", "S2"),
            candidate("action_area", 125.7, 7437, "opponent", "ACTION_AREA_ONSET", "a:s123"),
            candidate("meld", 126.2, 7467, "opponent", "MELD_DELTA", "m:s123", "S1,S2,S3"),
        ])
        self.assertEqual(report["status"], "ORDERED_CANDIDATES_ONLY")
        self.assertEqual(len(report["ledger"]), 11)
        times = [row["timestamp_seconds"] for row in report["ledger"]]
        self.assertEqual(times, sorted(times))
        # Reviewed claim pairs must come from the other actor. Otherwise the
        # later temporal assembler would correctly reject them as self-claims.
        by_ref = {row["candidate_kind"] + ":" + str(row["frame_index"]): row
                  for row in report["ledger"]}
        self.assertEqual(report["ledger"][5]["actor_hint"], "player")
        self.assertEqual(report["ledger"][7]["actor_hint"], "opponent")
        self.assertEqual(report["ledger"][8]["actor_hint"], "player")
        self.assertEqual(report["ledger"][10]["actor_hint"], "opponent")
        onset_rows = [row for row in report["ledger"] if row["channel"] == "action_area"]
        self.assertTrue(onset_rows)
        self.assertTrue(all(row["ledger_kind"] == "UNKNOWN" for row in onset_rows))
        self.assertTrue(all(row["evidence_grade"] == "UNKNOWN" for row in report["ledger"]))
        self.assertTrue(all(not row["runtime_action"] for row in report["ledger"]))
        self.assertFalse(report["formal_promotion_evidence"])
        self.assertFalse(report["safe_for_runtime"])
        self.assertFalse(report["safe_for_hint"])
        self.assertFalse(report["safe_for_executor"])


if __name__ == "__main__":
    unittest.main()
