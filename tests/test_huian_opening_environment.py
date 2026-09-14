import unittest

from huian import HuianEnvironment, UnknownRuleError
from huian._legacy import env


class OpeningEnvironmentTests(unittest.TestCase):
    def test_begin_opening_is_seeded_auditable_and_stops_at_qiangjin(self):
        first, second = HuianEnvironment(), HuianEnvironment()
        first.reset(seed=20260914)
        second.reset(seed=20260914)

        state = first.begin_opening(dice_total=7)
        matching = second.begin_opening(dice_total=7)

        self.assertEqual(state.state_hash(), matching.state_hash())
        self.assertEqual(state.phase, "OPENING_QIANGJIN_CHECK")
        self.assertEqual(state.current_player, state.dealer)
        self.assertEqual(len(state.hands[state.dealer]), 17)
        self.assertEqual(len(state.hands[1 - state.dealer]), 16)
        self.assertIn(state.gold_tile, env.BASE_TILES)
        self.assertEqual(sorted(state.physical_tiles()), sorted(env.full_wall()))
        self.assertEqual(first.events[0]["action"]["type"], "OPEN_GOLD")
        self.assertEqual(first.events[0]["action"]["metadata"]["dice_total"], 7)
        with self.assertRaises(UnknownRuleError) as raised:
            first.legal_actions()
        self.assertEqual(raised.exception.rule_ids, ("qiangjin",))

    def test_begin_opening_rejects_duplicate_or_invalid_request(self):
        game = HuianEnvironment()
        game.reset(seed=1)
        with self.assertRaises(ValueError):
            game.begin_opening(dice_total=1)
        game.begin_opening(dice_total=2)
        with self.assertRaises(ValueError):
            game.begin_opening(dice_total=2)


if __name__ == "__main__":
    unittest.main()