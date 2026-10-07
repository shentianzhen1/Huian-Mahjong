from __future__ import annotations

import unittest

from workspace.vision.runtime_public_adapter import current_snapshot_from_runtime


def gold_component(tile_id: str = "M5", *, reason: str = "accepted") -> dict:
    return {
        "normalized_bbox": [0.38, 0.82, 0.04, 0.10],
        "region_candidate": "gold",
        "gold_skin": True,
        "confidence": 0.96,
        "frame": 100,
        "candidate_tile_id": tile_id,
        "tile_id": tile_id,
        "tile_confidence": 0.96,
        "identity_reason": reason,
    }


def gold_observation(
    frame: int,
    tile_id: str = "M5",
    *,
    reason: str = "accepted",
) -> dict:
    return {
        "frame": frame,
        "candidate_tile_id": tile_id if tile_id != "UNKNOWN" else None,
        "tile_id": tile_id,
        "tile_confidence": 0.95 if tile_id != "UNKNOWN" else 0.0,
        "identity_reason": reason,
    }


def report(observations=None, **extra) -> dict:
    payload = {
        "schema_version": "vision_runtime_v0_2_smoke",
        "session": "gold-gate-session",
        "stream_epoch": 0,
        "frames": [98, 99, 100],
        "components": [gold_component()],
        "concealed_tile_count": 0,
        "all_concealed_tile_ids_trusted": False,
        "geometry_untrusted": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }
    if observations is not None:
        payload["gold_identity_observations"] = observations
    payload.update(extra)
    return payload


class RuntimeGoldMultiframeGateTests(unittest.TestCase):
    def test_same_gold_identity_across_distinct_frames_is_trusted(self):
        source = report([
            gold_observation(98, "M5"),
            gold_observation(99, "M5"),
            gold_observation(100, "M5"),
        ])

        snapshot = current_snapshot_from_runtime(source, timestamp_seconds=1.0)

        self.assertTrue(snapshot.gold_trusted)
        self.assertEqual(snapshot.gold_tile, "M5")
        self.assertNotIn("runtime_gold_not_fully_trusted", snapshot.adapter_issues)

    def test_conflicting_gold_identities_fail_closed_to_unknown(self):
        source = report([
            gold_observation(98, "M5"),
            gold_observation(99, "P5"),
            gold_observation(100, "M5"),
        ])

        snapshot = current_snapshot_from_runtime(source, timestamp_seconds=1.0)

        self.assertFalse(snapshot.gold_trusted)
        self.assertIsNone(snapshot.gold_tile)
        self.assertIn("runtime_gold_identity_conflict", snapshot.adapter_issues)

    def test_any_untrusted_frame_blocks_gold_promotion(self):
        source = report([
            gold_observation(98, "M5"),
            gold_observation(
                99,
                "UNKNOWN",
                reason="below_confidence_threshold",
            ),
            gold_observation(100, "M5"),
        ])

        snapshot = current_snapshot_from_runtime(source, timestamp_seconds=1.0)

        self.assertFalse(snapshot.gold_trusted)
        self.assertIsNone(snapshot.gold_tile)
        self.assertIn("runtime_gold_frame_identity_untrusted", snapshot.adapter_issues)

    def test_hidden_opening_metadata_cannot_infer_missing_live_gold(self):
        source = report(
            None,
            dice_total=8,
            opening_wall_index=27,
            random_seed=12345,
            inferred_gold_tile="M5",
        )

        snapshot = current_snapshot_from_runtime(source, timestamp_seconds=1.0)

        self.assertFalse(snapshot.gold_trusted)
        self.assertIsNone(snapshot.gold_tile)
        self.assertIn("runtime_gold_multiframe_evidence_missing", snapshot.adapter_issues)

    def test_duplicate_frame_ids_do_not_count_as_multiframe_identity(self):
        source = report([
            gold_observation(98, "M5"),
            gold_observation(98, "M5"),
        ])

        snapshot = current_snapshot_from_runtime(source, timestamp_seconds=1.0)

        self.assertFalse(snapshot.gold_trusted)
        self.assertIsNone(snapshot.gold_tile)
        self.assertIn("runtime_gold_frame_scope_conflict", snapshot.adapter_issues)


if __name__ == "__main__":
    unittest.main()
