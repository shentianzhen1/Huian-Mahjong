from collections import Counter
from copy import deepcopy
import random
import unittest

from huian import HuianEnvironment
from huian._compat.qzcore import tiles


def reference_multiset(values, include_flowers):
    allowed = set(tiles.BASE_TILES) | (set(tiles.FLOWERS) if include_flowers else set())
    bad = [tile for tile in values if tile not in allowed]
    if bad:
        return False, f"未知牌编码: {bad}"
    for tile, count in Counter(values).items():
        if tile in tiles.BASE_TILES and count > 4:
            return False, f"{tiles.CN.get(tile, tile)} 出现 {count} 张，超过4张"
        if tile in tiles.FLOWERS and count > 1:
            return False, f"花牌 {tiles.CN.get(tile, tile)} 重复出现"
    return True, "OK"


class HotPathCompatibilityTests(unittest.TestCase):
    def test_iterator_keeps_all_unknown_tiles_and_their_order(self):
        values = ['M1', 'BAD', 'P2', 'OTHER', 'BAD']
        self.assertEqual(tiles.validate_tile_multiset(iter(values)),
                         reference_multiset(values, True))

    def test_iterator_rejects_fifth_copy_of_every_standard_tile(self):
        for tile in tiles.BASE_TILES:
            with self.subTest(tile=tile):
                values = [tile] * 5
                self.assertEqual(tiles.validate_tile_multiset(iter(values)),
                                 reference_multiset(values, True))

    def test_iterator_checks_flower_repeats_and_disabled_flowers(self):
        for flower in tiles.FLOWERS:
            for include_flowers in (False, True):
                with self.subTest(tile=flower, include_flowers=include_flowers):
                    values = [flower, flower]
                    self.assertEqual(tiles.validate_tile_multiset(iter(values), include_flowers),
                                     reference_multiset(values, include_flowers))

    def test_unknown_diagnostic_precedes_overfull_tiles(self):
        values = ['M1'] * 5 + ['BAD']
        self.assertEqual(tiles.validate_tile_multiset(iter(values)),
                         reference_multiset(values, True))

    def test_sequence_and_single_pass_inputs_follow_same_contract(self):
        rng = random.Random(132)
        alphabet = list(tiles.BASE_TILES) + list(tiles.FLOWERS) + ['BAD']
        for include_flowers in (False, True):
            for _ in range(1000):
                values = [rng.choice(alphabet) for _ in range(rng.randrange(30))]
                expected = reference_multiset(values, include_flowers)
                for supplied in (values, tuple(values), iter(values)):
                    self.assertEqual(tiles.validate_tile_multiset(supplied, include_flowers), expected)

    def test_tile_index_preserves_tuple_lookup_contract(self):
        class UnhashableString(str):
            __hash__ = None

        class EqualToM1:
            __hash__ = None
            def __eq__(self, other):
                return other == 'M1'

        for value in (*tiles.BASE_TILES, UnhashableString('M1'), EqualToM1()):
            self.assertEqual(tiles.tile_index(value), tiles.BASE_TILES.index(value))
        for invalid in (None, True, 1, [], {}, 'BAD', UnhashableString('BAD')):
            with self.subTest(value=invalid):
                with self.assertRaises(ValueError) as expected:
                    tiles.BASE_TILES.index(invalid)
                with self.assertRaises(ValueError) as actual:
                    tiles.tile_index(invalid)
                self.assertEqual(str(actual.exception), str(expected.exception))

    def test_validation_does_not_mutate_ordinary_flower_or_wall_draw_state(self):
        for seed in range(5):
            game = HuianEnvironment()
            ready = game.reset(seed=seed)
            opened = game.begin_opening(2)
            states = [ready, opened]
            flower = next((tile for tile in opened.wall if tile in tiles.FLOWERS), None)
            if flower is not None:
                replacement = deepcopy(opened)
                replacement.wall.remove(flower)
                replacement.wall.append(replacement.hands[replacement.current_player].pop())
                replacement.hands[replacement.current_player].append(flower)
                replacement.phase = 'NEED_FLOWER_REPLACE'
                states.append(replacement)
            wall_draw = deepcopy(opened)
            while len(wall_draw.wall) > 16:
                tile = wall_draw.wall.pop()
                zone = wall_draw.flowers if tile in tiles.FLOWERS else wall_draw.discards
                zone[0].append(tile)
            wall_draw.phase = 'TERMINAL'
            wall_draw.terminal = True
            wall_draw.terminal_reason = 'WALL_16'
            states.append(wall_draw)
            for state in states:
                with self.subTest(seed=seed, phase=state.phase):
                    before = deepcopy(state)
                    game.rules.validate_state(state)
                    self.assertEqual(state, before)


if __name__ == '__main__':
    unittest.main()
