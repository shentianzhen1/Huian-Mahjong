import unittest
from collections import Counter

from huian._legacy import env
from workspace.ai import (MatchObservationContext, PlayerObservation,
                          estimate_ordinary_deal_in_probabilities,
                          estimate_tenpai_wait_loss_scores,
                          estimate_tenpai_wait_risk_scores)


def one_unknown_m1_observation(gold_tile=None, *, with_match_context=False):
    own = ("M1", "P1")
    opponent_melds = (
        ("PENG", ("M2", "M2", "M2")),
        ("PENG", ("M3", "M3", "M3")),
        ("PENG", ("M4", "M4", "M4")),
        ("PENG", ("P2", "P2", "P2")),
        ("PENG", ("P3", "P3", "P3")),
    )
    known = Counter(own)
    for _, tiles in opponent_melds:
        known.update(tiles)

    river = []
    for tile in env.BASE_TILES:
        target = 3 if tile == "M1" else 4
        river.extend([tile] * (target - known[tile]))

    match_context = (
        MatchObservationContext(
            scores=(1000, 1000), hand_index=2, hands_remaining=6,
            dealer=0, current_dealer_base=20, consecutive_dealer_hands=3,
        )
        if with_match_context else None
    )
    return PlayerObservation(
        seat=0, hand=own, gold_tile=gold_tile, phase="AFTER_DRAW",
        dealer=0, wall_remaining=1,
        discards=(tuple(river), ()),
        flowers=((), ()),
        melds=((), opponent_melds),
        match_context=match_context,
    )


class OpponentModelTests(unittest.TestCase):
    def test_exact_one_unknown_tile_gives_exact_probabilities(self):
        view = one_unknown_m1_observation()
        estimates = estimate_ordinary_deal_in_probabilities(
            view, ("M1", "P1"), samples=8, seed=9)
        by_tile = {item.tile: item for item in estimates}
        self.assertEqual(by_tile["M1"].opponent_open_melds, 5)
        self.assertEqual(by_tile["M1"].opponent_concealed_count, 1)
        self.assertEqual(by_tile["M1"].winning_samples, 8)
        self.assertEqual(by_tile["M1"].probability, 1.0)
        self.assertEqual(by_tile["P1"].winning_samples, 0)
        self.assertEqual(by_tile["P1"].probability, 0.0)

    def test_discarded_gold_and_single_gold_discard_hu_are_blocked(self):
        view = one_unknown_m1_observation(gold_tile="M1")
        estimates = estimate_ordinary_deal_in_probabilities(
            view, ("M1", "P1"), samples=8, seed=2)
        by_tile = {item.tile: item for item in estimates}
        self.assertEqual(by_tile["M1"].probability, 0.0)
        # Sampled opponent holds the only unseen M1 gold. P1 could be used
        # structurally with that wildcard, but target-room single-gold Ron is blocked.
        self.assertEqual(by_tile["P1"].probability, 0.0)

    def test_estimate_is_deterministic_for_seed_and_uses_common_sample_count(self):
        view = PlayerObservation(
            seat=0,
            hand=("M1","M2","M3","M4","M5","M6","P1","P2","P3",
                  "P4","P5","S1","S2","S3","E","E","R"),
            gold_tile="P9", phase="AFTER_DRAW", dealer=0, wall_remaining=60,
            discards=(("N",), ("W",)), flowers=((), ()), melds=((), ()),
        )
        first = estimate_ordinary_deal_in_probabilities(
            view, ("M1", "R"), samples=12, seed=17)
        second = estimate_ordinary_deal_in_probabilities(
            view, ("M1", "R"), samples=12, seed=17)
        self.assertEqual(first, second)
        self.assertTrue(all(item.samples == 12 for item in first))
        self.assertTrue(all(0.0 <= item.probability <= 1.0 for item in first))

    def test_tenpai_conditioned_score_is_exact_when_only_one_prehard_tile_is_possible(self):
        view = one_unknown_m1_observation()
        scores = estimate_tenpai_wait_risk_scores(
            view, ("M1", "P1"), samples=8, seed=4)
        by_tile = {item.tile: item for item in scores}
        self.assertEqual(by_tile["M1"].risk_score, 1.0)
        self.assertEqual(by_tile["M1"].matching_templates, 8)
        self.assertEqual(by_tile["M1"].templates_used, 8)
        self.assertEqual(by_tile["P1"].risk_score, 0.0)
        self.assertFalse(by_tile["M1"].is_deal_in_probability)
        self.assertGreaterEqual(by_tile["M1"].generation_attempts, 8)

    def test_tenpai_conditioned_score_respects_gold_ron_blocks(self):
        view = one_unknown_m1_observation(gold_tile="M1")
        scores = estimate_tenpai_wait_risk_scores(
            view, ("M1", "P1"), samples=6, seed=5)
        by_tile = {item.tile: item for item in scores}
        self.assertEqual(by_tile["M1"].risk_score, 0.0)
        self.assertEqual(by_tile["P1"].risk_score, 0.0)

    def test_tenpai_conditioned_score_is_seed_deterministic(self):
        view = PlayerObservation(
            seat=0,
            hand=("M1","M2","M3","M4","M5","M6","P1","P2","P3",
                  "P4","P5","S1","S2","S3","E","E","R"),
            gold_tile="P9", phase="AFTER_DRAW", dealer=0, wall_remaining=60,
            discards=(("N",), ("W",)), flowers=((), ()), melds=((), ()),
        )
        first = estimate_tenpai_wait_risk_scores(
            view, ("M1", "R"), samples=12, seed=19)
        second = estimate_tenpai_wait_risk_scores(
            view, ("M1", "R"), samples=12, seed=19)
        self.assertEqual(first, second)
        self.assertTrue(all(0.0 <= item.risk_score <= 1.0 for item in first))
        self.assertTrue(all(item.templates_used == 12 for item in first))

    def test_tenpai_conditioned_loss_uses_confirmed_pinghu_score(self):
        view = one_unknown_m1_observation(with_match_context=True)
        estimates = estimate_tenpai_wait_loss_scores(
            view, ("M1", "P1"), samples=8, seed=4)
        by_tile = {item.tile: item for item in estimates}
        self.assertTrue(by_tile["M1"].complete)
        self.assertEqual(by_tile["M1"].risk_score, 1.0)
        self.assertEqual(by_tile["M1"].loss_index, 20.0)
        self.assertEqual(by_tile["M1"].mean_loss_if_hit, 20.0)
        self.assertEqual(by_tile["M1"].scored_matching_templates, 8)
        self.assertFalse(by_tile["M1"].is_absolute_ev)
        self.assertTrue(by_tile["P1"].complete)
        self.assertEqual(by_tile["P1"].risk_score, 0.0)
        self.assertEqual(by_tile["P1"].loss_index, 0.0)
        self.assertEqual(by_tile["P1"].mean_loss_if_hit, 0.0)

    def test_tenpai_conditioned_loss_requires_match_context(self):
        with self.assertRaisesRegex(ValueError, "match_context"):
            estimate_tenpai_wait_loss_scores(
                one_unknown_m1_observation(), ("M1",), samples=4, seed=1)

    def test_invalid_inputs_and_impossible_public_counts_are_rejected(self):
        view = PlayerObservation(
            0, ("M1",), None, "AFTER_DRAW", 0, 40,
            (("M1","M1","M1","M1"), ()), ((), ()), ((), ()),
        )
        with self.assertRaises(ValueError):
            estimate_ordinary_deal_in_probabilities(
                view, ("M1",), samples=4, seed=1)
        clean = PlayerObservation(
            0, ("M1",), None, "AFTER_DRAW", 0, 40,
            ((), ()), ((), ()), ((), ()),
        )
        for samples in (0, -1, True):
            with self.subTest(samples=samples), self.assertRaises(ValueError):
                estimate_ordinary_deal_in_probabilities(
                    clean, ("M1",), samples=samples, seed=1)
        with self.assertRaises(ValueError):
            estimate_ordinary_deal_in_probabilities(
                clean, ("P1",), samples=4, seed=1)
        with self.assertRaises(ValueError):
            estimate_tenpai_wait_risk_scores(
                clean, ("P1",), samples=4, seed=1)
        with self.assertRaises(ValueError):
            estimate_tenpai_wait_risk_scores(
                clean, ("M1",), samples=0, seed=1)


if __name__ == "__main__":
    unittest.main()
