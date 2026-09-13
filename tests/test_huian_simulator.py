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

if __name__ == "__main__":
    unittest.main()
