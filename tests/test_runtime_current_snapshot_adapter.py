import unittest

from workspace.vision.current_state_snapshot import (
    SnapshotCapability,
    SnapshotStatus,
    assess_current_snapshot,
)
from workspace.vision.public_observers import (
    MeldGroup,
    MeldSnapshot,
    PublicTile,
    RiverSnapshot,
)
from workspace.vision.runtime_public_adapter import current_snapshot_from_runtime


HAND = (
    "M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8",
    "M9", "P1", "P2", "P3", "S1", "S2", "S3", "E",
)


def component(region, tile, index=0, *, accepted=True):
    return {
        "region_candidate": region,
        "tile_id": tile,
        "identity_reason": "accepted" if accepted else "below_confidence_threshold",
        "normalized_bbox": [0.02 + index * 0.04, 0.80, 0.035, 0.10],
        "confidence": 0.95,
        "frame": 102,
    }


def gold_observation(frame, tile):
    return {
        "frame": frame,
        "candidate_tile_id": tile,
        "tile_id": tile,
        "tile_confidence": 0.95,
        "identity_reason": "accepted",
    }


def report(hand=HAND, *, gold="B", session="runtime-a", epoch=0, melds=()):
    concealed = [component("hand", tile, i) for i, tile in enumerate(hand)]
    meld_components = [
        component("meld", tile, len(concealed) + i)
        for i, tile in enumerate(melds)
    ]
    gold_component = [component("gold", gold, len(concealed) + len(melds))]
    return {
        "schema_version": "vision_runtime_v0_2_smoke",
        "session": session,
        "stream_epoch": epoch,
        "frames": [100, 101, 102],
        "components": [*concealed, *meld_components, *gold_component],
        "gold_identity_observations": [
            gold_observation(frame, gold) for frame in (100, 101, 102)
        ],
        "concealed_tile_count": len(concealed),
        "all_concealed_tile_ids_trusted": all(tile != "UNKNOWN" for tile in hand),
        "geometry_untrusted": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def river(actor, tiles, *, session="runtime-a", epoch=0, trusted=True):
    return RiverSnapshot(
        timestamp_seconds=2.0,
        actor=actor,
        tiles=tuple(
            PublicTile((0.1 + i * 0.05, 0.2, 0.04, 0.08), tile)
            for i, tile in enumerate(tiles)
        ),
        trusted=trusted,
        source_session=session,
        stream_epoch=epoch,
    )


def meld(actor, groups, *, session="runtime-a", epoch=0, trusted=True):
    return MeldSnapshot(
        timestamp_seconds=2.0,
        actor=actor,
        groups=tuple(
            MeldGroup((0.1 + i * 0.2, 0.3, 0.15, 0.1), tuple(tiles))
            for i, tiles in enumerate(groups)
        ),
        trusted=trusted,
        source_session=session,
        stream_epoch=epoch,
    )


class RuntimeCurrentSnapshotAdapterTests(unittest.TestCase):
    def test_hand_gold_and_player_meld_count_enable_basic_shanten(self):
        snapshot = current_snapshot_from_runtime(report(), timestamp_seconds=2.0)
        result = assess_current_snapshot(snapshot)
        self.assertEqual(result.status, SnapshotStatus.PARTIAL)
        self.assertTrue(result.allows(SnapshotCapability.SHANTEN))
        self.assertFalse(result.allows(SnapshotCapability.DANGER_HINT))
        self.assertIn("player_river_missing", result.issues)

    def test_unknown_hand_or_unaccepted_gold_blocks_shanten(self):
        unknown = list(HAND)
        unknown[-1] = "UNKNOWN"
        hand_result = assess_current_snapshot(
            current_snapshot_from_runtime(
                report(tuple(unknown)), timestamp_seconds=2.0
            )
        )
        self.assertEqual(hand_result.status, SnapshotStatus.BLOCKED)

        gold_report = report()
        gold_report["components"][-1]["identity_reason"] = "below_confidence_threshold"
        gold_result = assess_current_snapshot(
            current_snapshot_from_runtime(gold_report, timestamp_seconds=2.0)
        )
        self.assertIn("gold_untrusted", gold_result.issues)
        self.assertFalse(gold_result.allows(SnapshotCapability.SHANTEN))

    def test_multiframe_gold_consensus_establishes_opened_gold_identity(self):
        source = report(gold="B")
        snapshot = current_snapshot_from_runtime(source, timestamp_seconds=2.0)
        self.assertEqual(snapshot.gold_tile, "B")
        self.assertTrue(snapshot.gold_trusted)

        source["gold_identity_observations"][1] = gold_observation(101, "R")
        conflict = current_snapshot_from_runtime(source, timestamp_seconds=2.0)
        self.assertIsNone(conflict.gold_tile)
        self.assertFalse(conflict.gold_trusted)
        self.assertIn("runtime_gold_identity_conflict", conflict.adapter_issues)

    def test_unknown_player_meld_identities_still_preserve_meld_count(self):
        snapshot = current_snapshot_from_runtime(
            report(HAND[:-3], melds=("UNKNOWN", "UNKNOWN", "UNKNOWN")),
            timestamp_seconds=2.0,
        )
        result = assess_current_snapshot(snapshot)
        self.assertTrue(result.allows(SnapshotCapability.SHANTEN))
        self.assertEqual(len(snapshot.melds[0]), 1)
        self.assertIn("meld_identity_unknown:0", result.issues)
        self.assertFalse(result.allows(SnapshotCapability.VISIBLE_REMAINDERS))

    def test_complete_same_source_public_state_enables_danger(self):
        snapshot = current_snapshot_from_runtime(
            report(),
            timestamp_seconds=2.0,
            player_river=river("player", ("P4", "P5")),
            opponent_river=river("opponent", ("S4", "S5")),
            opponent_meld=meld("opponent", (("S6", "S7", "S8"),)),
        )
        result = assess_current_snapshot(snapshot)
        self.assertEqual(result.status, SnapshotStatus.READY)
        self.assertTrue(result.allows(SnapshotCapability.DANGER_HINT))

    def test_cross_source_public_observation_is_dropped(self):
        snapshot = current_snapshot_from_runtime(
            report(),
            timestamp_seconds=2.0,
            player_river=river("player", ("P4",)),
            opponent_river=river("opponent", ("S4",), session="other"),
            opponent_meld=meld("opponent", (("S6", "S7", "S8"),)),
        )
        result = assess_current_snapshot(snapshot)
        self.assertTrue(result.allows(SnapshotCapability.SHANTEN))
        self.assertFalse(result.allows(SnapshotCapability.DANGER_HINT))
        self.assertIn("opponent_river_source_conflict", result.issues)
        self.assertEqual(snapshot.rivers[1], ())

    def test_runtime_physical_conflict_is_blocked_by_snapshot_gate(self):
        conflicting_hand = ("M1", "M1", "M1", "M1", *HAND[4:])
        snapshot = current_snapshot_from_runtime(
            report(conflicting_hand),
            timestamp_seconds=2.0,
            player_river=river("player", ("M1",)),
            opponent_river=river("opponent", ()),
            opponent_meld=meld("opponent", ()),
        )
        result = assess_current_snapshot(snapshot)
        self.assertEqual(result.status, SnapshotStatus.BLOCKED)
        self.assertIn("physical_copy_overflow:M1", result.issues)


if __name__ == "__main__":
    unittest.main()
