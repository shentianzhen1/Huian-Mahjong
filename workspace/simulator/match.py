"""Eight-hand match score accounting.

Player-confirmed target-room match contract (2026-09-18):
- 2 players.
- 8 hands by default.
- Each player starts at 1000 points.
- Every settled hand transfers a zero-sum reward between the two scores.
- The optimization target is the final score after hand 8, not single-hand win rate.

This module deliberately does not invent unresolved hand settlement. It only
aggregates already-settled reward vectors.
"""
from dataclasses import dataclass
from numbers import Integral

from huian.rules.dealer_base import (
    MATCH_HAND_COUNT, MATCH_STARTING_SCORE, MATCH_TOTAL_SCORE,
    dealer_base_for_consecutive_hands, next_consecutive_dealer_hands,
)


def _score_int(value, name):
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer")


@dataclass(frozen=True)
class MatchScoreState:
    """Immutable score ledger for the fixed two-player, eight-hand match."""

    scores: tuple[int, int] = (MATCH_STARTING_SCORE, MATCH_STARTING_SCORE)
    hands_played: int = 0

    def __post_init__(self):
        if (not isinstance(self.scores, tuple) or len(self.scores) != 2
                or any(isinstance(v, bool) or not isinstance(v, Integral)
                       for v in self.scores)):
            raise ValueError("scores must be a two-integer tuple")
        if sum(self.scores) != MATCH_TOTAL_SCORE:
            raise ValueError("match scores must conserve the initial 2000 points")
        if (isinstance(self.hands_played, bool)
                or not isinstance(self.hands_played, Integral)
                or not 0 <= self.hands_played <= MATCH_HAND_COUNT):
            raise ValueError("hands_played must be inside the 8-hand match")

    @classmethod
    def initial(cls):
        return cls()

    @property
    def hands_remaining(self):
        return MATCH_HAND_COUNT - self.hands_played

    @property
    def complete(self):
        return self.hands_played == MATCH_HAND_COUNT

    @property
    def margin(self):
        """Seat-0 score minus seat-1 score; positive means seat 0 leads."""
        return self.scores[0] - self.scores[1]

    def score_for(self, seat):
        if seat not in (0, 1) or isinstance(seat, bool):
            raise ValueError("seat must be 0 or 1")
        return self.scores[seat]

    def margin_for(self, seat):
        if seat not in (0, 1) or isinstance(seat, bool):
            raise ValueError("seat must be 0 or 1")
        return self.margin if seat == 0 else -self.margin

    def apply_hand(self, rewards):
        """Apply one already-settled zero-sum hand result."""
        if self.complete:
            raise ValueError("the 8-hand match is already complete")
        try:
            reward0, reward1 = rewards
        except (TypeError, ValueError) as exc:
            raise ValueError("rewards must contain exactly two integers") from exc
        _score_int(reward0, "reward0")
        _score_int(reward1, "reward1")
        if reward0 + reward1 != 0:
            raise ValueError("hand rewards must be zero-sum")
        return MatchScoreState(
            (self.scores[0] + reward0, self.scores[1] + reward1),
            self.hands_played + 1,
        )


@dataclass(frozen=True)
class MatchProgressState:
    """Eight-hand match ledger plus dealer/continuation state.

    The next hand's current dealer base is derived from the confirmed sitting
    base 5 and +5 for each consecutive dealer hand. Dealer stays after a dealer
    win or a draw; a dealer loss transfers dealer to the opponent.
    """

    score_state: MatchScoreState = MatchScoreState()
    dealer: int = 0
    consecutive_dealer_hands: int = 1

    def __post_init__(self):
        if type(self.dealer) is not int or self.dealer not in (0, 1):
            raise ValueError("dealer must be seat 0 or 1")
        if (type(self.consecutive_dealer_hands) is not int
                or self.consecutive_dealer_hands < 1):
            raise ValueError("consecutive_dealer_hands must be >= 1")
        if not isinstance(self.score_state, MatchScoreState):
            raise TypeError("score_state must be MatchScoreState")

    @classmethod
    def initial(cls, dealer=0):
        return cls(MatchScoreState.initial(), dealer, 1)

    @property
    def hand_index(self):
        return self.score_state.hands_played

    @property
    def hands_remaining(self):
        return self.score_state.hands_remaining

    @property
    def complete(self):
        return self.score_state.complete

    @property
    def scores(self):
        return self.score_state.scores

    @property
    def current_dealer_base(self):
        if self.complete:
            raise ValueError("completed match has no next-hand dealer base")
        return dealer_base_for_consecutive_hands(self.consecutive_dealer_hands)

    def apply_settled_hand(self, rewards, *, winner):
        """Advance one fully settled hand.

        winner is seat 0/1 for a win and None for a draw. Rewards are already
        real zero-sum settlement values; this method never invents missing fees.
        """
        if self.complete:
            raise ValueError("the 8-hand match is already complete")
        if winner is not None and (type(winner) is not int or winner not in (0, 1)):
            raise ValueError("winner must be seat 0, seat 1 or None")
        next_scores = self.score_state.apply_hand(rewards)
        dealer_stays = winner is None or winner == self.dealer
        next_dealer = self.dealer if dealer_stays else 1 - self.dealer
        next_consecutive = next_consecutive_dealer_hands(
            self.consecutive_dealer_hands, dealer_stays=dealer_stays
        )
        return MatchProgressState(
            next_scores, next_dealer, next_consecutive
        )


def score_eight_hand_match(hand_rewards):
    """Aggregate exactly eight settled hand reward vectors."""
    rewards = tuple(hand_rewards)
    if len(rewards) != MATCH_HAND_COUNT:
        raise ValueError("an evaluated match must contain exactly 8 hands")
    state = MatchScoreState.initial()
    for hand in rewards:
        state = state.apply_hand(hand)
    return state
