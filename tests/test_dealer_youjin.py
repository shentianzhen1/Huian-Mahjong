import unittest

from huian import HuianRules, YoujinStage
from huian.rules.dealer_base import (
    DEALER_WIN_MULTIPLIER,
    MATCH_HAND_COUNT,
    dealer_base_for_consecutive_hands,
    match_hand_in_range,
    next_consecutive_dealer_hands,
)


class DealerBaseTests(unittest.TestCase):
    def test_uncapped_repeat_sequence_runs_through_all_eight_hands(self):
        # Player confirmation 2026-09-19: if the same dealer keeps the seat,
        # dealer base has no cap inside the fixed eight-hand match.
        expected = [10, 15, 20, 25, 30, 35, 40, 45]
        for n, base in enumerate(expected, start=1):
            self.assertEqual(dealer_base_for_consecutive_hands(n), base)
            self.assertTrue(match_hand_in_range(n - 1))
        self.assertEqual(MATCH_HAND_COUNT, 8)
        self.assertEqual(expected[-1], 10 + 5 * 7)
        with self.assertRaises(ValueError):
            match_hand_in_range(8)
        with self.assertRaises(ValueError):
            dealer_base_for_consecutive_hands(0)

    def test_stay_increments_loss_resets(self):
        self.assertEqual(next_consecutive_dealer_hands(3, dealer_stays=True), 4)
        self.assertEqual(next_consecutive_dealer_hands(3, dealer_stays=False), 1)


class YoujinDealerMultiplierTests(unittest.TestCase):
    def setUp(self):
        self.rules = HuianRules()

    def test_dealer_triple_you_is_608_without_extra_times_two(self):
        self.assertEqual(DEALER_WIN_MULTIPLIER, 1)
        terms = self.rules.youjin_score_terms(
            YoujinStage.TRIPLE_YOU, winner=0, dealer=0, winner_fan=3
        )
        self.assertEqual(terms.dealer_multiplier, 1)
        self.assertEqual(terms.total_for_current_dealer_base(35), 608)
        idle = self.rules.youjin_score_terms(
            YoujinStage.TRIPLE_YOU, winner=1, dealer=0, winner_fan=3
        )
        self.assertEqual(idle.total_for_current_dealer_base(35), 608)
