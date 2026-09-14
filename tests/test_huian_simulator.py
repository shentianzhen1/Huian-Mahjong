import unittest

from workspace.simulator import Simulator, make_wall


class SimulatorTests(unittest.TestCase):
    def test_seed_reproduces_wall_and_inventory(self):
        wall = make_wall(42)
        self.assertEqual(wall, make_wall(42))
        self.assertEqual(len(wall), 144)
        self.assertTrue(all(wall.count(tile) <= 4 for tile in set(wall)))

    def test_unknown_opening_stops_explicitly(self):
        result = Simulator().run(seed=42)
        self.assertEqual(result.status, "UNRESOLVED")
        self.assertTrue(result.unresolved)

    def test_opening_trace_is_reproducible_and_stops_at_qiangjin(self):
        first = Simulator().run_opening(seed=42)
        second = Simulator().run_opening(seed=42)
        self.assertEqual(first, second)
        self.assertEqual(first.status, "STOPPED_UNKNOWN")
        self.assertEqual(first.phase, "OPENING_QIANGJIN_CHECK")
        self.assertEqual(first.unresolved, (
            "qiangjin_hand_shape", "qiangjin_seat_priority", "qiangjin_settlement",
        ))
        self.assertEqual(len(first.events), 1)
        self.assertEqual(first.events[0]["action"]["type"], "OPEN_GOLD")
        self.assertIn(first.dice_total, range(2, 13))
        self.assertGreater(first.wall_remaining, 16)

    def test_explicit_dice_value_is_replayed(self):
        result = Simulator().run_opening(seed=99, dice_total=7)
        self.assertEqual(result.dice_total, 7)
        self.assertEqual(result.events[0]["action"]["metadata"]["dice_total"], 7)


if __name__ == "__main__":
    unittest.main()