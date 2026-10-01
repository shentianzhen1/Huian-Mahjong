import unittest

from workspace.vision.issue69_public_replay_adapters import (
    action_area_report_candidates,
    river_report_candidates,
)


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

    def test_action_area_stays_context_only(self):
        report = {
            "schema_version": "source_action_area_geometry_v0_1",
            "source_session": "s",
            "source_sha256": "b" * 64,
            "candidates": [{
                "frame": 444,
                "region_actor_hint": "player",
                "tile": "UNKNOWN",
                "action_kind": "UNKNOWN",
            }],
        }
        rows = action_area_report_candidates(report)
        self.assertEqual(rows[0].channel, "action_area")
        self.assertEqual(rows[0].kind, "ACTION_AREA_ONSET")
        self.assertIsNone(rows[0].tile)


if __name__ == "__main__":
    unittest.main()
