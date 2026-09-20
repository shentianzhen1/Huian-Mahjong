"""Sitting dealer base and consecutive-dealer increment.

Player wording 2026-09-15/18: "sitting dealer base +5, each keep +5".
Direct full-match replay match_evidence_001 (2026-09-19) resolves the screen/settlement
mapping: non-dealer own base is 5, while the first sitting dealer's CURRENT
SETTLEMENT BASE is 10; every consecutive dealer hand adds another 5.
The observed chain is 10 -> 15 -> 20 -> 25, and a dealer change resets the new
dealer's settlement base to 10. Player confirmation 2026-09-19 resolves the
remaining boundary: while the SAME dealer keeps the dealer seat, there is no
dealer-base cap; each consecutive dealer hand adds +5 until the fixed 8-hand
match ends. If the dealer loses, the chain ends and the new dealer resets to 10.
Dealer-win extra ×2 is not used.
"""
from numbers import Integral

NON_DEALER_BASE = 5
DEALER_ENTRY_INCREMENT = 5
SITTING_DEALER_BASE = NON_DEALER_BASE + DEALER_ENTRY_INCREMENT  # 10
REPEAT_DEALER_INCREMENT = 5
MATCH_HAND_COUNT = 8
MATCH_STARTING_SCORE = 1000
MATCH_TOTAL_SCORE = MATCH_STARTING_SCORE * 2
DEALER_WIN_MULTIPLIER = 1


def _nonneg(value, name):
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")


def dealer_base_for_consecutive_hands(consecutive_dealer_hands):
    """Base for the hand about to be played.

    ``consecutive_dealer_hands`` is 1 on first sit, 2 after one keep, ...
    Direct match_evidence_001 evidence gives 10, 15, 20, 25 for consecutive counts
    1..4. Player confirmation 2026-09-19 confirms no cap while the same dealer
    continues: counts 1..8 are 10,15,20,25,30,35,40,45. If the dealer loses,
    the consecutive count resets to 1, so the new dealer starts again at 10.
    """
    _nonneg(consecutive_dealer_hands, "consecutive_dealer_hands")
    if consecutive_dealer_hands < 1:
        raise ValueError("consecutive_dealer_hands must be >= 1")
    return SITTING_DEALER_BASE + REPEAT_DEALER_INCREMENT * (consecutive_dealer_hands - 1)


def next_consecutive_dealer_hands(consecutive_dealer_hands, *, dealer_stays):
    """Dealer stays on win or draw; after a dealer loss the opponent sits at 1.

    A new dealer at count 1 settles with current dealer base 10 in the target
    room; the other player's own displayed base remains 5.
    """
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
