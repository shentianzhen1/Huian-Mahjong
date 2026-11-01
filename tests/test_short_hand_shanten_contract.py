"""Synthetic advisory contract; does not certify real-video identities."""
from dataclasses import replace
import unittest

from workspace.hint_alpha import analyze_snapshot_shanten
from workspace.vision.current_state_snapshot import CurrentTableSnapshot


def short_snapshot(post_draw=False):
    hand = ("E", "P1", "P2", "P3", "P6", "P6", "M1")
    return CurrentTableSnapshot(
        timestamp_seconds=1.0, source_session="synthetic_short_hand",
        stream_epoch=0, stable_frames=5,
        own_hand=hand + (("N",) if post_draw else ()), gold_tile="E",
        rivers=((), ()), melds=(((None, None, None),) * 3, ()),
        hand_trusted=True, gold_trusted=True,
        river_trusted=(False, False), meld_trusted=(True, False),
    )


class ShortHandShantenContractTests(unittest.TestCase):
    def test_three_unknown_identity_structural_groups_allow_seven_pre_draw(self):
        result = analyze_snapshot_shanten(short_snapshot())
        self.assertTrue(result.allowed)
        self.assertEqual(result.phase, "PRE_DRAW")
        self.assertFalse(result.visible_remainders_used)
        self.assertFalse(result.safe_for_executor)

    def test_eight_post_draw_allows_structural_discard_analysis(self):
        result = analyze_snapshot_shanten(short_snapshot(True))
        self.assertTrue(result.allowed)
        self.assertEqual(result.phase, "POST_DRAW")
        self.assertTrue(result.best_discards)
        self.assertFalse(result.visible_remainders_used)

    def test_untrusted_count_blocks(self):
        result = analyze_snapshot_shanten(replace(short_snapshot(), meld_trusted=(False, False)))
        self.assertFalse(result.allowed)
        self.assertIn("player_meld_count_untrusted", result.issues)

    def test_only_two_groups_do_not_authorize_seven_tiles(self):
        original = short_snapshot()
        result = analyze_snapshot_shanten(replace(original, melds=(original.melds[0][:2], ())))
        self.assertFalse(result.allowed)
        self.assertIn("concealed_hand_count_invalid", result.issues)

    def test_missing_hand_identity_or_gold_blocks(self):
        original = short_snapshot()
        self.assertFalse(analyze_snapshot_shanten(replace(original, own_hand=(None,) + original.own_hand[1:])).allowed)
        self.assertFalse(analyze_snapshot_shanten(replace(original, gold_trusted=False)).allowed)
