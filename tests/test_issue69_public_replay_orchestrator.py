import unittest

from workspace.vision.issue69_public_replay_orchestrator import (
    PublicReplayCandidate,
    assemble_public_replay_candidates,
)

SHA = "a" * 64


def row(channel, ts, frame, actor, kind, ref, tile=None, *, tiles=(), sha=SHA, epoch=0):
    return PublicReplayCandidate(
        channel=channel,
        timestamp_seconds=ts,
        frame_index=frame,
        actor_hint=actor,
        kind=kind,
        source_session="reviewed_hand",
        source_sha256=sha,
        stream_epoch=epoch,
        evidence_refs=(ref,),
        tile=tile,
    )


class Issue69PublicReplayOrchestratorTests(unittest.TestCase):
    def test_orders_independent_channels_without_promoting_action_area(self):
        report = assemble_public_replay_candidates([
            row("meld", 10.4, 104, "player", "MELD_DELTA", "meld:104"),
            row("action_area", 10.2, 102, "player", "ACTION_AREA_ONSET", "action:102"),
            row("river", 10.0, 100, "opponent", "DISCARD", "river:100", "S5"),
        ])
        self.assertEqual(report["status"], "ORDERED_CANDIDATES_ONLY")
        self.assertEqual(
            [item["channel"] for item in report["ledger"]],
            ["river", "action_area", "meld"],
        )
        onset = report["ledger"][1]
        self.assertEqual(onset["candidate_kind"], "ACTION_AREA_ONSET")
        self.assertEqual(onset["ledger_kind"], "UNKNOWN")
        self.assertIsNone(onset["tile"])
        self.assertTrue(all(not item["runtime_action"] for item in report["ledger"]))
        self.assertFalse(report["safe_for_runtime"])
        self.assertFalse(report["safe_for_hint"])
        self.assertFalse(report["safe_for_executor"])

    def test_rejects_cross_source_or_epoch_mix(self):
        with self.assertRaisesRegex(ValueError, "exact source scope"):
            assemble_public_replay_candidates([
                row("river", 1, 1, "player", "DISCARD", "r1"),
                row("meld", 2, 2, "player", "MELD_DELTA", "m2", epoch=1),
            ])

    def test_rejects_reused_evidence_between_channels(self):
        with self.assertRaisesRegex(ValueError, "must not be reused"):
            assemble_public_replay_candidates([
                row("river", 1, 1, "player", "DISCARD", "same"),
                row("meld", 2, 2, "player", "MELD_DELTA", "same"),
            ])

    def test_surfaces_same_frame_public_actor_conflict(self):
        report = assemble_public_replay_candidates([
            row("river", 5, 50, "opponent", "DISCARD", "r50"),
            row("meld", 5, 50, "player", "MELD_DELTA", "m50"),
        ])
        self.assertEqual(report["status"], "CONFLICT")
        self.assertEqual(
            report["conflicts"][0]["reason"],
            "conflicting_public_actor_hints_same_frame",
        )

    def test_correlates_removed_river_tile_with_opposite_actor_peng(self):
        report = assemble_public_replay_candidates([
            row("river", 115.0, 3450, "opponent", "RIVER_TILE_REMOVED_OR_CLAIMED", "river:3450"),
            row("meld", 115.4, 3462, "player", "MELD_DELTA", "meld:3462", tiles=("M9","M9","M9")),
        ])
        claim = report["corroborated_claims"][0]
        self.assertEqual(claim["action"], "PENG")
        self.assertEqual(claim["actor"], "player")
        self.assertEqual(claim["claimed_from_actor"], "opponent")
        self.assertFalse(report["safe_for_runtime"])
        self.assertFalse(report["safe_for_executor"])

    def test_incomplete_meld_identity_remains_unknown_claim(self):
        report = assemble_public_replay_candidates([
            row("river", 129.0, 3870, "opponent", "RIVER_TILE_REMOVED_OR_CLAIMED", "river:3870"),
            row("meld", 129.4, 3882, "player", "MELD_DELTA", "meld:3882", tiles=(None,"S3","S4")),
        ])
        self.assertEqual(report["corroborated_claims"][0]["action"], "UNKNOWN_CLAIM")

    def test_empty_input_fails_closed(self):
        report = assemble_public_replay_candidates([])
        self.assertEqual(report["status"], "EMPTY")
        self.assertEqual(report["ledger"], [])
        self.assertFalse(report["safe_for_runtime"])


if __name__ == "__main__":
    unittest.main()
