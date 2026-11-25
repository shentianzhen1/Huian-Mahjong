import unittest

from workspace.vision.issue69_public_replay_adapters import (
    action_area_report_candidates,
    river_report_candidates,
    meld_observation_candidate,
)
from workspace.vision.public_match_reconstruction import ObservationKind, RawObservation


class Issue69PublicReplayAdapterTests(unittest.TestCase):
    def test_river_report_preserves_unknown_identity_and_frame_provenance(self):
        report = {
            "schema_version": "source_river_action_replay_v0_1",
            "source_session": "s",
            "source_sha256": "a" * 64,
            "machine_predictions": {"actions": [{
                "timestamp_seconds": 12.5,
                "stream_epoch": 0,
                "kind": "DISCARD",
                "actor": "opponent",
                "evidence_refs": ["river_growth:frame:321"],
                "tile": None,
            }]},
        }
        rows = river_report_candidates(report)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].frame_index, 321)
        self.assertEqual(rows[0].actor_hint, "opponent")
        self.assertIsNone(rows[0].tile)

    def test_river_report_includes_exact_single_removal(self):
        report = {
            "schema_version": "source_river_action_replay_v0_1",
            "source_session": "s", "source_sha256": "a" * 64,
            "machine_predictions": {"actions": []},
            "river_removals": [{
                "timestamp_seconds": 117.2, "frame_index": 3516,
                "stream_epoch": 0, "actor": "player",
                "evidence_refs": ["public:s:frame:3516"], "tile": None,
            }],
        }
        rows = river_report_candidates(report)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].kind, "RIVER_TILE_REMOVED_OR_CLAIMED")
        self.assertEqual(rows[0].actor_hint, "player")

    def test_river_report_refuses_to_guess_missing_frame(self):
        report = {
            "schema_version": "source_river_action_replay_v0_1",
            "source_session": "s",
            "source_sha256": "a" * 64,
            "machine_predictions": {"actions": [{
                "timestamp_seconds": 1,
                "stream_epoch": 0,
                "kind": "DISCARD",
                "actor": "player",
                "evidence_refs": ["river_growth"],
                "tile": None,
            }]},
        }
        with self.assertRaisesRegex(ValueError, "exact source frame"):
            river_report_candidates(report)

    def test_accumulated_river_refs_use_explicit_event_frame(self):
        report = {
            "schema_version": "source_river_action_replay_v0_1",
            "source_session": "s", "source_sha256": "a" * 64,
            "machine_predictions": {"actions": [{
                "timestamp_seconds": 3.8, "frame_index": 114,
                "stream_epoch": 0, "kind": "DISCARD", "actor": "player",
                "evidence_refs": ["public:s:frame:19", "public:s:frame:114"],
                "tile": None,
            }]},
        }
        self.assertEqual(river_report_candidates(report)[0].frame_index, 114)
        del report["machine_predictions"]["actions"][0]["frame_index"]
        with self.assertRaisesRegex(ValueError, "one exact source frame"):
            river_report_candidates(report)

    def test_action_area_stays_context_only(self):
        report = {
            "schema_version": "source_action_area_geometry_v0_1",
            "source_session": "s",
            "source_sha256": "b" * 64,
            "candidates": [{
                "frame": 444,
                "timestamp_seconds": 14.8,
                "region_actor_hint": "player",
                "tile": "UNKNOWN",
                "action_kind": "UNKNOWN",
            }],
        }
        rows = action_area_report_candidates(report)
        self.assertEqual(rows[0].channel, "action_area")
        self.assertEqual(rows[0].kind, "ACTION_AREA_ONSET")
        self.assertEqual(rows[0].timestamp_seconds, 14.8)
        self.assertIsNone(rows[0].tile)

    def test_action_area_legacy_frame_as_seconds_is_rejected(self):
        report = {
            "schema_version": "source_action_area_geometry_v0_1",
            "source_session": "s", "source_sha256": "b" * 64,
            "candidates": [{"frame": 444, "region_actor_hint": "player"}],
        }
        with self.assertRaisesRegex(ValueError, "source PTS seconds"):
            action_area_report_candidates(report)

    def test_meld_observation_preserves_complete_group_identity(self):
        obs = RawObservation(
            timestamp_seconds=20.5,
            actor="opponent",
            kind=ObservationKind.MELD_DELTA,
            confidence=.9,
            tiles=("S1", "S2", "S3"),
            evidence_refs=("meld-track-7",),
            details={
                "frame": 777,
                "source_session": "s",
                "stream_epoch": 0,
                "tile_identity_complete": True,
            },
        )
        row = meld_observation_candidate(obs, source_sha256="c" * 64)
        self.assertEqual(row.channel, "meld")
        self.assertEqual(row.frame_index, 777)
        self.assertEqual(row.tile, "S1,S2,S3")
        self.assertEqual(row.tiles, ("S1", "S2", "S3"))

    def test_meld_partial_identity_remains_unknown(self):
        obs = RawObservation(
            timestamp_seconds=20.5,
            actor="player",
            kind=ObservationKind.MELD_DELTA,
            confidence=.7,
            tiles=(),
            evidence_refs=("meld-track-8",),
            details={
                "frame": 778,
                "source_session": "s",
                "stream_epoch": 0,
                "tile_identity_complete": False,
            },
        )
        row = meld_observation_candidate(obs, source_sha256="d" * 64)
        self.assertIsNone(row.tile)

    def test_meld_three_to_four_upgrade_preserves_previous_group_metadata(self):
        obs = RawObservation(
            timestamp_seconds=112.1, actor="player", kind=ObservationKind.MELD_DELTA,
            confidence=.9, tiles=("S8",) * 4, evidence_refs=("meld-upgrade",),
            details={
                "frame": 3363, "source_session": "s", "stream_epoch": 0,
                "group_size": 4, "previous_group_size": 3,
                "previous_meld": ["S8"] * 3, "tile_identity_complete": True,
                "tile_candidates": ["S8"] * 4,
            },
        )
        row = meld_observation_candidate(obs, source_sha256="e" * 64)
        self.assertEqual(row.meld_group_size, 4)
        self.assertEqual(row.previous_meld_group_size, 3)
        self.assertEqual(row.previous_meld, ("S8",) * 3)
        self.assertEqual(row.tiles, ("S8",) * 4)

    def test_meld_unknown_identity_still_preserves_three_to_four_shape(self):
        obs = RawObservation(
            timestamp_seconds=112.1, actor="player", kind=ObservationKind.MELD_DELTA,
            confidence=.9, tiles=(), evidence_refs=("meld-upgrade-unknown",),
            details={
                "frame": 3363, "source_session": "s", "stream_epoch": 0,
                "group_size": 4, "previous_group_size": 3, "previous_meld": [],
                "tile_identity_complete": False,
                "tile_candidates": [None, None, None, None],
            },
        )
        row = meld_observation_candidate(obs, source_sha256="f" * 64)
        self.assertEqual(row.tiles, (None, None, None, None))
        self.assertEqual(row.meld_group_size, 4)
        self.assertEqual(row.previous_meld_group_size, 3)
        self.assertEqual(row.previous_meld, ())


if __name__ == "__main__":
    unittest.main()
