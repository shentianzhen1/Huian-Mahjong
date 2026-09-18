"""Sitting dealer base and consecutive-dealer increment.

Player confirmation 2026-09-15/18: sitting base 5, each keep +5.
No cap inside the 8-hand match. Dealer-win extra ×2 is not used.
"""
from numbers import Integral

SITTING_DEALER_BASE = 5
REPEAT_DEALER_INCREMENT = 5
MATCH_HAND_COUNT = 8
DEALER_WIN_MULTIPLIER = 1


def _nonneg(value, name):
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")


def dealer_base_for_consecutive_hands(consecutive_dealer_hands):
    """Base for the hand about to be played.

    ``consecutive_dealer_hands`` is 1 on first sit, 2 after one keep, ...
    Eighth consecutive hand in one match is 5 + 5*7 = 40. No cap.
    """
    _nonneg(consecutive_dealer_hands, "consecutive_dealer_hands")
    if consecutive_dealer_hands < 1:
        raise ValueError("consecutive_dealer_hands must be >= 1")
    return SITTING_DEALER_BASE + REPEAT_DEALER_INCREMENT * (consecutive_dealer_hands - 1)


def next_consecutive_dealer_hands(consecutive_dealer_hands, *, dealer_stays):
    """Dealer stays on win or draw; loser of a dealer loss sits at 1."""
    _nonneg(consecutive_dealer_hands, "consecutive_dealer_hands")
    if dealer_stays:
        return consecutive_dealer_hands + 1
    return 1


def match_hand_in_range(hand_index):
    """``hand_index`` is 0..7 for an 8-hand match."""
    _nonneg(hand_index, "hand_index")
    if hand_index >= MATCH_HAND_COUNT:
        raise ValueError("hand_index must be inside the 8-hand match")
    return True
