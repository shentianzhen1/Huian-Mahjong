import unittest

from huian._legacy import env
from huian.environment.opening import GoldIndicator, deal_initial_hands, locate_gold_indicator, plan_opening


class OpeningTests(unittest.TestCase):
    def test_deal_has_dealer_17_idle_16_and_conserves_wall(self):
        wall = env.full_wall()
        hands, remaining = deal_initial_hands(wall, dealer=1)
        self.assertEqual((len(hands[0]), len(hands[1])), (16, 17))
        self.assertEqual(len(remaining), 111)
        self.assertEqual(sorted(hands[0] + hands[1] + remaining), sorted(wall))
        self.assertEqual(len(wall), 144)

    def test_dice_stack_location_and_flower_skip_are_explicit(self):
        wall = ["M1", "M2", "F1", "F2", "P9", "S9"]
        # N=2 starts at index 3 (the top of the second stack from the tail),
        # then skips its flower toward the tail to P9.
        indicator = locate_gold_indicator(wall, 2)
        self.assertEqual(indicator, GoldIndicator("P9", 4, ("F2",)))

    def test_opening_runs_replacement_before_indicator_lookup(self):
        wall = env.full_wall()
        flower_index = wall.index("F1")
        wall[0], wall[flower_index] = wall[flower_index], wall[0]
        plan = plan_opening(wall, dealer=0, dice_total=2)
        self.assertEqual(len(plan.hands[0]), 17)
        self.assertEqual(len(plan.hands[1]), 16)
        self.assertTrue(plan.gold_indicator.tile in env.BASE_TILES)
        self.assertEqual(
            len(plan.wall) + sum(map(len, plan.hands))
            + sum(map(len, plan.flowers)) + 1,
            144,
        )
        self.assertEqual(
            plan.wall.count(plan.gold_indicator.tile)
            + sum(hand.count(plan.gold_indicator.tile) for hand in plan.hands),
            3,
        )

    def test_invalid_dice_and_short_wall_are_rejected(self):
        with self.assertRaises(ValueError):
            locate_gold_indicator(env.full_wall(), 1)
        with self.assertRaises(ValueError):
            deal_initial_hands([], dealer=0)


if __name__ == "__main__":
    unittest.main()
