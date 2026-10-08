from __future__ import annotations

import unittest

from workspace.hint_alpha import analyze_snapshot_shanten
from workspace.vision.current_state_snapshot import CurrentTableSnapshot


TENPAI = (
    "M1", "M1", "M1",
    "P1", "P1", "P1",
    "S1", "S1", "S1",
    "E", "E", "E",
    "R", "R", "R",
    "B",
)
POST_DRAW = (
    "M1", "M1", "M1",
    "P1", "P1", "P1",
    "S1", "S1", "S1",
    "E", "E", "E",
    "R", "R", "R",
    "B", "N",
)
COUNT_ONLY_HAND = (
    "M6", "M6", "P3", "P4", "P5",
    "P5", "P7", "P7", "P9", "P9",
)


def snapshot(
    hand=TENPAI,
    *,
    public_trusted=False,
    hand_trusted=True,
    gold_trusted=True,
):
    return CurrentTableSnapshot(
        timestamp_seconds=2.0,
        source_session="session_a",
        stream_epoch=0,
        stable_frames=3,
        own_hand=tuple(hand),
        gold_tile="P9",
        rivers=((), ()),
        melds=((), ()),
        hand_trusted=hand_trusted,
        gold_trusted=gold_trusted,
        river_trusted=(public_trusted, public_trusted),
        meld_trusted=(True, public_trusted),
    )


def count_only_snapshot(*, input_source: str, meld_slot: tuple[None, ...]):
    manual = input_source == "user_entered"
    return CurrentTableSnapshot(
        timestamp_seconds=2.0,
        source_session="manual:count-only" if manual else "runtime-count-only",
        stream_epoch=0,
        stable_frames=0 if manual else 3,
        own_hand=COUNT_ONLY_HAND,
        gold_tile="M6",
        rivers=((), ()),
        melds=((meld_slot, meld_slot), ()),
        hand_trusted=True,
        gold_trusted=True,
        river_trusted=(False, False),
        meld_trusted=(True, False),
        adapter_issues=("user_entered_unverified",) if manual else (),
        input_source=input_source,
    )


class CurrentSnapshotShantenAdvisorTests(unittest.TestCase):
    def test_partial_pre_draw_returns_structural_shanten_only(self):
        result = analyze_snapshot_shanten(snapshot())
        self.assertTrue(result.allowed)
        self.assertEqual(result.status, "PARTIAL")
        self.assertEqual(result.phase, "PRE_DRAW")
        self.assertEqual(result.shanten, 0)
        self.assertEqual(result.effective_tiles, ())
        self.assertFalse(result.visible_remainders_used)
        self.assertFalse(result.safe_for_executor)

    def test_ready_pre_draw_adds_live_effective_tile_counts(self):
        result = analyze_snapshot_shanten(snapshot(public_trusted=True))
        self.assertTrue(result.allowed)
        self.assertEqual(result.status, "READY")
        self.assertEqual(result.phase, "PRE_DRAW")
        self.assertEqual(result.shanten, 0)
        self.assertTrue(result.effective_tiles)
        self.assertTrue(all(item.remaining > 0 for item in result.effective_tiles))
        self.assertTrue(result.visible_remainders_used)

    def test_unknown_hand_blocks_all_shanten_output(self):
        unknown = list(TENPAI)
        unknown[-1] = None
        result = analyze_snapshot_shanten(
            snapshot(tuple(unknown), hand_trusted=False)
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.status, "BLOCKED")
        self.assertIsNone(result.phase)
        self.assertIsNone(result.shanten)
        self.assertEqual(result.best_discards, ())
        self.assertIn("hand_untrusted", result.issues)
        self.assertIn("hand_identity_unknown", result.issues)

    def test_partial_post_draw_returns_minimum_shanten_discards_without_live_counts(self):
        result = analyze_snapshot_shanten(snapshot(POST_DRAW))
        self.assertTrue(result.allowed)
        self.assertEqual(result.phase, "POST_DRAW")
        self.assertTrue(result.best_discards)
        self.assertEqual(
            len({item.shanten for item in result.best_discards}),
            1,
        )
        self.assertTrue(
            all(item.total_live_copies is None for item in result.best_discards)
        )
        self.assertFalse(result.visible_remainders_used)

    def test_ready_post_draw_can_attach_public_live_copy_metrics(self):
        result = analyze_snapshot_shanten(
            snapshot(POST_DRAW, public_trusted=True)
        )
        self.assertTrue(result.allowed)
        self.assertEqual(result.phase, "POST_DRAW")
        self.assertTrue(result.best_discards)
        self.assertTrue(
            all(item.total_live_copies is not None for item in result.best_discards)
        )
        self.assertTrue(result.visible_remainders_used)

    def test_complete_post_draw_does_not_suggest_discard(self):
        complete = (*TENPAI[:-1], "B", "B")
        self.assertEqual(len(complete), 17)
        result = analyze_snapshot_shanten(
            snapshot(complete, public_trusted=True)
        )
        self.assertTrue(result.allowed)
        self.assertEqual(result.phase, "POST_DRAW_COMPLETE")
        self.assertEqual(result.shanten, -1)
        self.assertEqual(result.best_discards, ())
        self.assertFalse(result.safe_for_executor)

    def test_count_only_meld_encodings_match_structural_shanten(self):
        manual = analyze_snapshot_shanten(
            count_only_snapshot(
                input_source="user_entered",
                meld_slot=(None,),
            )
        )
        runtime = analyze_snapshot_shanten(
            count_only_snapshot(
                input_source="runtime_vision",
                meld_slot=(None, None, None),
            )
        )

        for result in (manual, runtime):
            self.assertTrue(result.allowed)
            self.assertEqual(result.status, "PARTIAL")
            self.assertEqual(result.phase, "PRE_DRAW")
            self.assertEqual(result.best_discards, ())
            self.assertFalse(result.visible_remainders_used)
            self.assertFalse(result.safe_for_executor)
            self.assertIn("meld_identity_unknown:0", result.issues)

        self.assertEqual(manual.shanten, runtime.shanten)

    def test_runtime_cannot_use_manual_count_only_slot(self):
        result = analyze_snapshot_shanten(
            count_only_snapshot(
                input_source="runtime_vision",
                meld_slot=(None,),
            )
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.status, "BLOCKED")
        self.assertIsNone(result.shanten)
        self.assertEqual(result.best_discards, ())
        self.assertIn("meld_shape_invalid:0:0", result.issues)


if __name__ == "__main__":
    unittest.main()
