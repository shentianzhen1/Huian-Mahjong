from __future__ import annotations

from collections import Counter
import random
import unittest

from huian import HuianEnvironment, HuianRules
from huian._compat import qzenv as env
from workspace.simulator.match import MatchProgressState


class CoreInvariantContractTests(unittest.TestCase):
    """Cross-cutting invariants that must survive future rule/state refactors."""

    def test_opening_conserves_all_144_tiles_and_caps_playable_gold_across_seeds(self):
        expected = Counter(env.full_wall())
        for seed in range(20):
            for dice_total in range(2, 13):
                with self.subTest(seed=seed, dice_total=dice_total):
                    game = HuianEnvironment()
                    game.reset(seed=seed, dealer=seed % 2)
                    state = game.begin_opening(dice_total)

                    self.assertEqual(Counter(state.physical_tiles()), expected)
                    self.assertEqual(state.reserved_tiles.count(state.gold_tile), 1)

                    playable_gold = state.wall.count(state.gold_tile)
                    playable_gold += sum(
                        hand.count(state.gold_tile) for hand in state.hands
                    )
                    playable_gold += sum(
                        river.count(state.gold_tile) for river in state.discards
                    )
                    playable_gold += sum(
                        sum(meld.tiles.count(state.gold_tile) for meld in melds)
                        for melds in state.melds
                    )
                    self.assertLessEqual(playable_gold, 3)

    def test_every_standard_tile_rejects_a_fifth_physical_copy(self):
        rules = HuianRules()
        for tile in env.BASE_TILES:
            with self.subTest(tile=tile):
                with self.assertRaises(ValueError):
                    rules.validate_tiles([tile] * 5)

    def test_randomized_eight_hand_ledgers_stay_zero_sum_and_monotonic(self):
        rng = random.Random(20260922)
        for sample in range(100):
            match = MatchProgressState.initial(dealer=sample % 2)
            previous_hand = match.hand_index

            for _ in range(8):
                if rng.random() < 0.20:
                    rewards = (0, 0)
                    winner = None
                else:
                    transfer = rng.randint(1, 120)
                    winner = rng.randrange(2)
                    rewards = (
                        (transfer, -transfer)
                        if winner == 0
                        else (-transfer, transfer)
                    )

                match = match.apply_settled_hand(rewards, winner=winner)
                self.assertEqual(sum(match.scores), 2000)
                self.assertEqual(match.hand_index, previous_hand + 1)
                self.assertGreaterEqual(match.hands_remaining, 0)
                previous_hand = match.hand_index

            self.assertTrue(match.complete)
            self.assertEqual(match.hand_index, 8)
            self.assertEqual(match.hands_remaining, 0)


if __name__ == "__main__":
    unittest.main()
