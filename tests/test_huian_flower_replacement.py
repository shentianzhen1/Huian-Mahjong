import unittest

from huian.environment.flowers import replace_flowers


class FlowerReplacementTests(unittest.TestCase):
    def test_dealer_first_and_new_flower_waits_for_next_round(self):
        # list tail is the final element: dealer draws M8 then F4, idle draws S9;
        # F4 waits until the next dealer-to-idle round and is then replaced by P9.
        result = replace_flowers(
            hands=[["F1", "M1", "F2"], ["F3", "P1"]],
            flowers=[[], []],
            wall=["M9", "P9", "S9", "F4", "M8"],
            dealer=0,
        )
        self.assertEqual([(event.player, event.round_number) for event in result.events],
                         [(0, 1), (1, 1), (0, 2)])
        self.assertEqual(result.events[0].replacements, ("M8", "F4"))
        self.assertEqual(result.events[1].replacements, ("S9",))
        self.assertEqual(result.events[2].flowers, ("F4",))
        self.assertEqual(result.hands, (("M1", "M8", "P9"), ("P1", "S9")))
        self.assertEqual(result.flowers, (("F1", "F2", "F4"), ("F3",)))
        self.assertEqual(result.wall, ("M9",))

    def test_idle_seat_can_be_dealer_and_inputs_are_not_mutated(self):
        hands = [["F1", "M1"], ["F2", "P1"]]
        flowers, wall = [[], []], ["M9", "P9"]
        result = replace_flowers(hands, flowers, wall, dealer=1)
        self.assertEqual([event.player for event in result.events], [1, 0])
        self.assertEqual(hands, [["F1", "M1"], ["F2", "P1"]])
        self.assertEqual(flowers, [[], []])
        self.assertEqual(wall, ["M9", "P9"])

    def test_non_flower_in_flower_zone_and_exhausted_tail_are_rejected(self):
        with self.assertRaises(ValueError):
            replace_flowers([[], []], [["M1"], []], [], dealer=0)
        with self.assertRaises(ValueError):
            replace_flowers([["F1"], []], [[], []], [], dealer=0)


if __name__ == "__main__":
    unittest.main()
