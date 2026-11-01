from __future__ import annotations

import unittest

from workspace.hint_alpha import analyze_snapshot_danger
from workspace.vision.current_state_snapshot import CurrentTableSnapshot


POST_DRAW = (
    "M1", "M1", "M1",
    "P1", "P1", "P1",
    "S1", "S1", "S1",
    "E", "E", "E",
    "R", "R", "R",
    "B", "N",
)
PRE_DRAW = POST_DRAW[:-1]


def snapshot(
    hand=POST_DRAW,
    *,
    public_trusted=True,
    rivers=(("B",), ("B",)),
):
    return CurrentTableSnapshot(
        timestamp_seconds=3.0,
        source_session="session_a",
        stream_epoch=0,
        stable_frames=3,
        own_hand=tuple(hand),
        gold_tile="P9",
        rivers=rivers,
        melds=((), ()),
        hand_trusted=True,
        gold_trusted=True,
        river_trusted=(public_trusted, public_trusted),
        meld_trusted=(True, public_trusted),
    )


class CurrentSnapshotDangerTests(unittest.TestCase):
    def test_untrusted_public_state_blocks_danger(self):
        result = analyze_snapshot_danger(
            snapshot(public_trusted=False),
            ("B", "N"),
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.items, ())
        self.assertFalse(result.safe_for_executor)

    def test_ready_post_draw_uses_transparent_unseen_copy_proxy(self):
        result = analyze_snapshot_danger(snapshot(), ("N", "B"))
        self.assertTrue(result.allowed)
        self.assertEqual([item.tile for item in result.items], ["B", "N"])
        by_tile = {item.tile: item for item in result.items}
        self.assertEqual(by_tile["B"].own_copies, 1)
        self.assertEqual(by_tile["B"].public_copies, 2)
        self.assertEqual(by_tile["B"].unseen_copies, 1)
        self.assertEqual(by_tile["B"].risk_units, 1)
        self.assertEqual(by_tile["B"].opponent_discard_copies, 1)
        self.assertEqual(by_tile["N"].unseen_copies, 3)
        self.assertFalse(by_tile["B"].is_probability)

    def test_pre_draw_snapshot_does_not_claim_discard_danger(self):
        result = analyze_snapshot_danger(snapshot(PRE_DRAW), ("B",))
        self.assertFalse(result.allowed)
        self.assertEqual(result.items, ())
        self.assertIn("discard_window_not_observed", result.issues)

    def test_gold_discard_is_explicitly_unsupported(self):
        hand = (*POST_DRAW[:-1], "P9")
        result = analyze_snapshot_danger(
            snapshot(hand, rivers=((), ())),
            ("P9", "B"),
        )
        self.assertTrue(result.allowed)
        self.assertEqual(result.unsupported_tiles, ("P9",))
        self.assertEqual([item.tile for item in result.items], ["B"])
        self.assertIn("gold_discard_special_state_unsupported", result.issues)

    def test_candidate_must_be_in_hand(self):
        with self.assertRaisesRegex(ValueError, "present in own hand"):
            analyze_snapshot_danger(snapshot(), ("M9",))


if __name__ == "__main__":
    unittest.main()
