import unittest
from dataclasses import replace

from workspace.vision.current_state_snapshot import (
    CurrentTableSnapshot,
    SnapshotCapability,
    SnapshotStatus,
    advisory_analysis_inputs,
    assess_current_snapshot,
)


class CurrentStateSnapshotTests(unittest.TestCase):
    def snapshot(self, **changes):
        base = CurrentTableSnapshot(
            timestamp_seconds=12.5,
            source_session="hand-1",
            stream_epoch=0,
            stable_frames=3,
            own_hand=(
                "M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8",
                "M9", "P1", "P2", "P3", "S1", "S2", "S3", "E",
            ),
            gold_tile="B",
            rivers=(("P4", "P5"), ("S4", "S5")),
            melds=((), (("S6", "S7", "S8"),)),
            hand_trusted=True,
            gold_trusted=True,
            river_trusted=(True, True),
            meld_trusted=(True, True),
        )
        return replace(base, **changes)

    def test_ready_snapshot_enables_all_advisory_capabilities(self):
        snapshot = self.snapshot()
        result = assess_current_snapshot(snapshot)
        self.assertEqual(result.status, SnapshotStatus.READY)
        self.assertEqual(
            result.capabilities,
            (
                SnapshotCapability.SHANTEN,
                SnapshotCapability.VISIBLE_REMAINDERS,
                SnapshotCapability.DANGER_HINT,
            ),
        )
        inputs = advisory_analysis_inputs(snapshot, result)
        self.assertEqual(inputs.open_meld_count, 0)
        self.assertEqual(inputs.gold_tile, "B")
        self.assertEqual(len(inputs.visible_tiles), 7)
        self.assertFalse(inputs.safe_for_executor)

    def test_public_unknown_keeps_basic_shanten_but_blocks_danger(self):
        snapshot = self.snapshot(
            rivers=(("P4", None), ("S4", "S5")),
            river_trusted=(False, True),
        )
        result = assess_current_snapshot(snapshot)
        self.assertEqual(result.status, SnapshotStatus.PARTIAL)
        self.assertTrue(result.allows(SnapshotCapability.SHANTEN))
        self.assertFalse(result.allows(SnapshotCapability.DANGER_HINT))
        self.assertIn("river_untrusted:0", result.issues)
        self.assertIsNone(advisory_analysis_inputs(snapshot, result).visible_tiles)

    def test_unknown_hand_or_gold_blocks_shanten(self):
        unknown_hand = self.snapshot(
            own_hand=(*self.snapshot().own_hand[:-1], None),
        )
        self.assertEqual(
            assess_current_snapshot(unknown_hand).status,
            SnapshotStatus.BLOCKED,
        )
        unknown_gold = self.snapshot(gold_tile=None, gold_trusted=False)
        self.assertFalse(
            assess_current_snapshot(unknown_gold).allows(
                SnapshotCapability.SHANTEN
            )
        )

    def test_unstable_or_unscoped_snapshot_blocks_everything(self):
        result = assess_current_snapshot(
            self.snapshot(source_session=None, stable_frames=1)
        )
        self.assertEqual(result.status, SnapshotStatus.BLOCKED)
        self.assertIn("source_session_missing", result.issues)
        self.assertIn("snapshot_not_stable", result.issues)

    def test_impossible_physical_count_blocks_all_capabilities(self):
        snapshot = self.snapshot(
            own_hand=("M1", "M1", "M1", "M1", *self.snapshot().own_hand[4:]),
            rivers=(("M1",), ()),
        )
        result = assess_current_snapshot(snapshot)
        self.assertEqual(result.status, SnapshotStatus.BLOCKED)
        self.assertIn("physical_copy_overflow:M1", result.issues)

    def test_opened_gold_has_at_most_three_playable_copies(self):
        snapshot = self.snapshot(
            own_hand=("B", "B", "B", *self.snapshot().own_hand[3:]),
            rivers=(("P4",), ("S4",)),
        )
        allowed = assess_current_snapshot(snapshot)
        self.assertNotIn("playable_gold_copy_overflow", allowed.issues)

        overflow = assess_current_snapshot(
            replace(snapshot, rivers=(("B",), ("S4",)))
        )
        self.assertIn("playable_gold_copy_overflow", overflow.issues)
        self.assertEqual(overflow.status, SnapshotStatus.BLOCKED)

    def test_concealed_count_uses_current_player_meld_count(self):
        snapshot = self.snapshot(
            own_hand=self.snapshot().own_hand[:-3],
            melds=((('P6', 'P6', 'P6'),), self.snapshot().melds[1]),
        )
        result = assess_current_snapshot(snapshot)
        self.assertTrue(result.allows(SnapshotCapability.SHANTEN))
        self.assertEqual(advisory_analysis_inputs(snapshot).open_meld_count, 1)

        bad = assess_current_snapshot(replace(snapshot, own_hand=("M1",) * 10))
        self.assertIn("concealed_hand_count_invalid", bad.issues)
        self.assertEqual(bad.status, SnapshotStatus.BLOCKED)

    def test_blocked_snapshot_cannot_build_analysis_inputs(self):
        with self.assertRaisesRegex(ValueError, "not trusted"):
            advisory_analysis_inputs(self.snapshot(hand_trusted=False))


if __name__ == "__main__":
    unittest.main()
