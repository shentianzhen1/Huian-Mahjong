"""Sanitized, source-reviewed first-hand terminal shape and score regression.

The final screenshot establishes the concealed faces and two public melds.
Flower identities are not visible here: F1/F2/F3 are distinct count tokens,
not a claim that these were the actual flowers. This is a terminal checkpoint,
not a full 144-tile turn-by-turn replay or Vision prediction.
"""
from collections import Counter
from types import SimpleNamespace
import unittest

from huian.rules import HuianRules
from huian.rules.config import RulesConfig
from huian.rules.context import YoujinStage


class FirstHandObservedTerminalTests(unittest.TestCase):
    def test_terminal_meld_shape_fan_and_zero_sum_68(self):
        rules = HuianRules(RulesConfig(settlement_model="current_dealer_plus_winner_v1"))
        # Final screen: two M6 Jin, 3P/4P/5P, 7P/7P/8P/9P/9P,
        # and the separated continuation draw 4P.
        concealed = ["M6", "M6", "P3", "P4", "P5", "P7", "P7",
                     "P8", "P9", "P9", "P4"]
        melds = (
            SimpleNamespace(kind="MING_GANG", tiles=("P6",) * 4),
            SimpleNamespace(kind="CHI", tiles=("S3", "S4", "S5")),
        )
        self.assertEqual(len(concealed), (5 - len(melds)) * 3 + 2)
        before_continuation_draw = concealed.copy()
        before_continuation_draw.remove("P4")
        self.assertTrue(rules.is_youjin_ready_hand(
            before_continuation_draw, "M6", open_melds=len(melds)))

        # The opened Jin indicator is a separate reserved physical tile.
        physical = Counter([*concealed, *(tile for m in melds for tile in m.tiles), "M6"])
        self.assertTrue(all(count <= 4 for count in physical.values()))
        self.assertEqual(physical["M6"], 3)
        self.assertEqual(physical["P6"], 4)

        # The losing player's revealed final row shows two CHI groups and a
        # 10-face concealed zone after its final discard; no unseen draw is
        # inserted to force an 11th face.
        opponent_concealed = ("P2", "P2", "P4", "P5", "P7",
                              "S2", "S3", "S4", "S5", "S6")
        opponent_melds = (("S4", "S5", "S6"), ("S1", "S2", "S3"))
        self.assertEqual(len(opponent_concealed), (5 - len(opponent_melds)) * 3 + 1)
        physical.update(opponent_concealed)
        for meld in opponent_melds:
            physical.update(meld)
        self.assertTrue(all(count <= 4 for count in physical.values()))

        fan = rules.aggregate_youjin_fan(
            concealed, melds=melds, flowers=("F1", "F2", "F3"), gold_tile="M6")
        self.assertTrue(fan.complete)
        self.assertEqual({part.category: part.fan for part in fan.components},
                         {"gold": 2, "flowers": 3, "kong": 2})
        self.assertEqual(fan.fan, 7)
        self.assertEqual(fan.decomposition_count, 1)
        terms = rules.youjin_score_terms(
            YoujinStage.YOUJIN, winner=0, dealer=0, winner_fan=fan.fan)
        base = rules.dealer_base_for_consecutive_hands(1)
        settlement = rules.settle(
            winner=0, current_dealer_base=base, winner_fan=fan.fan,
            multiplier=terms.youjin_multiplier)
        self.assertEqual((base, terms.youjin_multiplier), (10, 4))
        self.assertEqual(settlement.rewards, (68, -68))


if __name__ == "__main__":
    unittest.main()
