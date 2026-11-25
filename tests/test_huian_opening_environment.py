import unittest

from huian import HuianEnvironment, UnknownRuleError
from huian._legacy import env


class OpeningEnvironmentTests(unittest.TestCase):
    def test_legacy_begin_opening_is_seeded_auditable_and_stops_unknown(self):
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
        self.assertGreaterEqual(state.reserved_tiles.count(state.gold_tile), 1)
        playable_gold = state.wall.count(state.gold_tile)
        playable_gold += sum(hand.count(state.gold_tile) for hand in state.hands)
        playable_gold += sum(river.count(state.gold_tile) for river in state.discards)
        self.assertLessEqual(playable_gold, 3)
        self.assertEqual(sorted(state.physical_tiles()), sorted(env.full_wall()))
        self.assertEqual(first.events[0]["action"]["type"], "OPEN_GOLD")
        self.assertEqual(first.events[0]["action"]["metadata"]["dice_total"], 7)
        self.assertEqual(
            first.events[0]["action"]["metadata"]["location_evidence"],
            "SIMULATOR_CONVENTION",
        )
        self.assertTrue(
            first.events[0]["action"]["metadata"]["indicator_removed_from_drawable_wall"]
        )
        # This legacy dice-location path is deliberately not upgraded into the
        # player-confirmed first-round runtime. The staged API owns that path;
        # default simulator/live routing is a later migration step.
        report = first.action_report()
        self.assertTrue({
            "qiangjin_hand_shape", "qiangjin_seat_priority", "qiangjin_settlement"
        }.issubset(set(report.unresolved)))
        with self.assertRaises(UnknownRuleError):
            first.legal_actions()
        self.assertIsNone(state.first_round)

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
