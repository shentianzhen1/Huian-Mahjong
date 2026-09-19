import unittest

from workspace.ai import evaluate_tenpai_ordinary_value


class OrdinaryScoreValueTests(unittest.TestCase):
    def test_known_ordinary_wait_uses_real_fan_and_current_dealer_base(self):
        # Five natural concealed triplets + single B waiting for the pair.
        # M/P/S triplets = 1 fan each; E/R honor triplets = 2 each => 7 fan.
        hand = (
            ["M1"] * 3
            + ["P1"] * 3
            + ["S1"] * 3
            + ["E"] * 3
            + ["R"] * 3
            + ["B"]
        )
        value = evaluate_tenpai_ordinary_value(
            hand,
            gold_tile="M9",
            current_dealer_base=10,
            visible_tiles=("M9", "M9", "M9"),
        )
        self.assertFalse(value.is_full_ev)
        self.assertEqual(value.winning_tile_types, ("B",))
        self.assertEqual(value.total_live_copies, 3)
        self.assertEqual(value.draws[0].fan, 7)
        self.assertEqual(value.draws[0].net_points, 34)
        self.assertEqual(value.weighted_net_points, 102)
        self.assertEqual(value.mean_net_points_if_win, 34.0)

    def test_flower_and_exposed_honor_peng_are_included(self):
        # One fixed honor Peng + four concealed melds + single B.
        hand = (
            ["M1"] * 3
            + ["P1"] * 3
            + ["S1"] * 3
            + ["R"] * 3
            + ["B"]
        )
        value = evaluate_tenpai_ordinary_value(
            hand,
            gold_tile="M9",
            melds=(("PENG", ("E", "E", "E")),),
            flowers=("F1", "F2"),
            current_dealer_base=15,
            visible_tiles=("M9", "M9", "M9"),
        )
        # Concealed: 3 suited triplets + R honor triplet = 5 fan.
        # Exposed E Peng = 1, flowers = 2 => 8 fan.
        self.assertEqual(value.draws[0].fan, 8)
        self.assertEqual(value.draws[0].net_points, 46)
        self.assertEqual(value.mean_net_points_if_win, 46.0)

    def test_non_tenpai_hand_is_rejected(self):
        hand = (
            ["M1"] * 3
            + ["P1"] * 3
            + ["S1"] * 3
            + ["E"] * 3
            + ["B", "N", "M5", "M7"]
        )
        with self.assertRaisesRegex(ValueError, "shanten 0"):
            evaluate_tenpai_ordinary_value(
                hand,
                gold_tile="M9",
                current_dealer_base=10,
            )


if __name__ == "__main__":
    unittest.main()
