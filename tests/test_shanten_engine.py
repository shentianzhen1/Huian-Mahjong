import unittest

from huian import HuianRules
from workspace.ai import (
    analyze_effective_tiles,
    analyze_two_ply_offense,
    best_discard,
    best_offense_ties,
    min_shanten_discards,
    ordinary_shanten,
    rank_discards,
)


WIN = (
    ["M1"] * 3
    + ["P1"] * 3
    + ["S1"] * 3
    + ["E"] * 3
    + ["R"] * 3
    + ["B"] * 2
)


class HuianShantenTests(unittest.TestCase):
    def test_complete_and_tenpai_match_ordinary_structure(self):
        self.assertEqual(len(WIN), 17)
        self.assertTrue(HuianRules().analyze_hu(WIN).legal)
        self.assertEqual(ordinary_shanten(WIN), -1)

        tenpai = WIN[:-1]
        self.assertEqual(len(tenpai), 16)
        self.assertEqual(ordinary_shanten(tenpai), 0)
        analysis = analyze_effective_tiles(tenpai)
        self.assertEqual(analysis.shanten, 0)
        self.assertEqual(analysis.effective_tile_types, ("B",))
        self.assertEqual(analysis.total_live_copies, 3)
        self.assertTrue(analysis.effective_tiles[0].winning)

    def test_one_shanten_is_distinct_from_tenpai(self):
        hand = (
            ["M1"] * 3
            + ["P1"] * 3
            + ["S1"] * 3
            + ["E"] * 3
            + ["B"] * 2
            + ["M5", "N"]
        )
        self.assertEqual(len(hand), 16)
        analysis = analyze_effective_tiles(hand)
        self.assertEqual(analysis.shanten, 1)
        self.assertTrue(analysis.effective_tiles)
        self.assertTrue(all(
            item.next_shanten < analysis.shanten
            for item in analysis.effective_tiles
        ))

    def test_single_gold_with_five_complete_melds_waits_on_every_tile(self):
        gold = "P9"
        hand = (
            ["M1"] * 3
            + ["P1"] * 3
            + ["S1"] * 3
            + ["E"] * 3
            + ["R"] * 3
            + [gold]
        )
        self.assertEqual(len(hand), 16)
        analysis = analyze_effective_tiles(hand, gold_tile=gold)
        self.assertEqual(analysis.shanten, 0)
        self.assertEqual(len(analysis.effective_tile_types), 34)
        self.assertEqual(analysis.total_live_copies, 120)
        self.assertTrue(all(item.winning for item in analysis.effective_tiles))

    def test_gold_complete_hands_agree_with_rules_solver(self):
        for hand in (
            ["M1"] * 3 + ["P1"] * 3 + ["S1"] * 3
            + ["E"] * 3 + ["R"] * 3 + ["B", "P9"],
            ["M1"] * 3 + ["P1"] * 3 + ["S1"] * 3
            + ["E"] * 3 + ["R"] * 3 + ["P9", "P9"],
        ):
            self.assertTrue(HuianRules().analyze_hu(
                hand, gold_tile="P9").legal)
            self.assertEqual(ordinary_shanten(
                hand, gold_tile="P9"), -1)

    def test_fixed_open_meld_reduces_concealed_target(self):
        hand = (
            ["M1"] * 3
            + ["P1"] * 3
            + ["S1"] * 3
            + ["E"] * 3
            + ["B"]
        )
        self.assertEqual(len(hand), 13)
        analysis = analyze_effective_tiles(hand, open_melds=1)
        self.assertEqual(analysis.shanten, 0)
        self.assertEqual(analysis.effective_tile_types, ("B",))
        self.assertEqual(analysis.total_live_copies, 3)

    def test_public_tiles_can_turn_structural_wait_dead(self):
        tenpai = WIN[:-1]
        analysis = analyze_effective_tiles(
            tenpai, visible_tiles=("B", "B", "B"))
        self.assertEqual(analysis.shanten, 0)
        self.assertEqual(analysis.effective_tiles, ())
        self.assertEqual(analysis.total_live_copies, 0)

    def test_discard_ranking_uses_live_public_copy_counts(self):
        hand = (
            ["M1"] * 3
            + ["P1"] * 3
            + ["S1"] * 3
            + ["E"] * 3
            + ["R"] * 3
            + ["B", "N"]
        )
        ranked = rank_discards(
            hand, visible_tiles=("N", "N", "N"))
        self.assertEqual(ranked[0].discard, "N")
        self.assertEqual(ranked[0].shanten, 0)
        self.assertEqual(ranked[0].effective_tile_types, ("B",))
        self.assertEqual(ranked[0].total_live_copies, 3)

    def test_best_discard_matches_full_ranking_top_choice(self):
        hand = (
            ["M1"] * 3
            + ["P1"] * 3
            + ["S1"] * 3
            + ["E"] * 3
            + ["R"] * 3
            + ["B", "N"]
        )
        visible = ("N", "N", "N")
        full = rank_discards(hand, visible_tiles=visible)[0]
        fast = best_discard(hand, visible_tiles=visible)
        self.assertEqual(fast, full)
        restricted = best_discard(
            hand,
            visible_tiles=visible,
            allowed_discards=("B", "N"),
        )
        self.assertEqual(restricted, full)

    def test_best_offense_ties_remove_only_tile_order_tiebreak(self):
        hand = (
            ["M1"] * 3
            + ["P1"] * 3
            + ["S1"] * 3
            + ["E"] * 3
            + ["R"] * 3
            + ["B", "N"]
        )
        ties = best_offense_ties(hand)
        self.assertEqual({item.discard for item in ties}, {"B", "N"})
        self.assertEqual(len({item.shanten for item in ties}), 1)
        self.assertEqual(len({item.total_live_copies for item in ties}), 1)
        self.assertEqual(len({len(item.effective_tiles) for item in ties}), 1)
        # V0.3 still resolves the exact tie by canonical tile order.
        self.assertIn(best_discard(hand), ties)

    def test_best_offense_ties_exclude_weaker_live_copy_candidate(self):
        hand = (
            ["M1"] * 3
            + ["P1"] * 3
            + ["S1"] * 3
            + ["E"] * 3
            + ["R"] * 3
            + ["B", "N"]
        )
        ties = best_offense_ties(hand, visible_tiles=("N", "N"))
        self.assertEqual(tuple(item.discard for item in ties), ("N",))
        self.assertEqual(ties[0], best_discard(hand, visible_tiles=("N", "N")))

    def test_min_shanten_frontier_matches_best_discard_shanten(self):
        hand = (
            ["M1"] * 3
            + ["P1"] * 3
            + ["S1"] * 3
            + ["E"] * 3
            + ["R"] * 3
            + ["B", "N"]
        )
        visible = ("N", "N")
        best = best_discard(hand, visible_tiles=visible)
        frontier = min_shanten_discards(hand, visible_tiles=visible)
        self.assertTrue(frontier)
        self.assertEqual(frontier[0].shanten, best.shanten)
        self.assertTrue(all(item.shanten == best.shanten for item in frontier))
        self.assertEqual(
            max(item.total_live_copies for item in frontier),
            best.total_live_copies,
        )

    def test_two_ply_offense_is_deterministic_inside_exact_tie(self):
        hand = (
            ["M1"] * 3
            + ["P1"] * 3
            + ["S1"] * 3
            + ["E"] * 3
            + ["R"] * 3
            + ["B", "N"]
        )
        ties = best_offense_ties(hand)
        candidates = tuple(item.discard for item in ties)
        first = analyze_two_ply_offense(hand, candidates)
        second = analyze_two_ply_offense(hand, candidates)
        self.assertEqual(first, second)
        self.assertEqual({item.discard for item in first}, {"B", "N"})
        self.assertTrue(all(item.draw_copies == 119 for item in first))
        self.assertTrue(all(item.terminal_win_copies == 3 for item in first))
        self.assertTrue(all(
            isinstance(item.weighted_post_shanten, int)
            and isinstance(item.weighted_post_live_copies, int)
            and isinstance(item.weighted_post_effective_types, int)
            for item in first
        ))

    def test_two_ply_offense_respects_public_physical_counts(self):
        hand = (
            ["M1"] * 3
            + ["P1"] * 3
            + ["S1"] * 3
            + ["E"] * 3
            + ["R"] * 3
            + ["B", "N"]
        )
        result = analyze_two_ply_offense(
            hand, ("N",), visible_tiles=("B", "B"))
        self.assertEqual(len(result), 1)
        # 17 known base tiles in hand/discard plus two public B copies.
        self.assertEqual(result[0].draw_copies, 117)
        self.assertEqual(result[0].terminal_win_copies, 1)

    def test_input_shape_and_public_overcount_are_rejected(self):
        with self.assertRaises(ValueError):
            ordinary_shanten(["M1"] * 15)
        with self.assertRaises(ValueError):
            analyze_effective_tiles(WIN)
        with self.assertRaises(ValueError):
            rank_discards(WIN[:-1])
        with self.assertRaises(ValueError):
            analyze_effective_tiles(
                WIN[:-1], visible_tiles=("B", "B", "B", "B"))


if __name__ == "__main__":
    unittest.main()
