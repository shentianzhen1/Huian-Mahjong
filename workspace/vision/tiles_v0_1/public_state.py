"""Public match-state observations from the Huian replay/live UI.

This module deliberately separates *reading pixels* from *trusting state*.
Digit/OCR implementations may change, while these invariants remain stable:

- two-player target-room scores conserve 2000 points;
- hand number is 1..8 and never moves backwards in a live sequence;
- scores stay fixed during one hand and may change at the hand boundary;
- remaining wall count must not increase inside one hand;
- noisy one-frame reads are fused by short-window consensus.

Nothing in this module is Executor-safe. It only produces advisory observations.
"""
from collections import Counter
from dataclasses import dataclass
from numbers import Integral

from huian.rules.dealer_base import MATCH_HAND_COUNT, MATCH_TOTAL_SCORE


def _plain_int(value, name):
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer or None")


@dataclass(frozen=True)
class NormalizedBox:
    """Resolution-independent [0,1] crop box."""

    left: float
    top: float
    right: float
    bottom: float

    def __post_init__(self):
        values = (self.left, self.top, self.right, self.bottom)
        if any(isinstance(value, bool) for value in values):
            raise ValueError("normalized coordinates must be numeric")
        if not (0 <= self.left < self.right <= 1):
            raise ValueError("invalid horizontal normalized box")
        if not (0 <= self.top < self.bottom <= 1):
            raise ValueError("invalid vertical normalized box")

    def pixel_box(self, size):
        width, height = size
        if (
            isinstance(width, bool)
            or isinstance(height, bool)
            or not isinstance(width, Integral)
            or not isinstance(height, Integral)
            or width <= 0
            or height <= 0
        ):
            raise ValueError("size must contain positive integer width/height")
        left = int(round(self.left * width))
        top = int(round(self.top * height))
        right = int(round(self.right * width))
        bottom = int(round(self.bottom * height))
        return left, top, right, bottom

    def crop(self, image):
        return image.crop(self.pixel_box(image.size))


@dataclass(frozen=True)
class HuianPublicStateProfile:
    """Current target-room layout, expressed as normalized crops.

    Avatar pixels/nicknames are intentionally not read. The avatar panel is only
    a visual anchor; score ROIs are the numbers directly below the two avatars.
    """

    top_right_score: NormalizedBox = NormalizedBox(0.665, 0.160, 0.745, 0.188)
    bottom_left_score: NormalizedBox = NormalizedBox(0.080, 0.812, 0.170, 0.840)
    status_line: NormalizedBox = NormalizedBox(0.400, 0.780, 0.620, 0.845)

    def crops(self, image):
        return {
            "top_right_score": self.top_right_score.crop(image),
            "bottom_left_score": self.bottom_left_score.crop(image),
            "status_line": self.status_line.crop(image),
        }


@dataclass(frozen=True)
class PublicStateCandidate:
    """One frame's advisory UI read before temporal/physics validation."""

    top_right_score: int | None = None
    bottom_left_score: int | None = None
    hand_number: int | None = None
    remaining_tiles: int | None = None
    confidence: float = 1.0
    source_frame: str | None = None

    def __post_init__(self):
        _plain_int(self.top_right_score, "top_right_score")
        _plain_int(self.bottom_left_score, "bottom_left_score")
        _plain_int(self.hand_number, "hand_number")
        _plain_int(self.remaining_tiles, "remaining_tiles")
        if isinstance(self.confidence, bool) or not isinstance(
            self.confidence, (int, float)
        ):
            raise ValueError("confidence must be numeric")
        if not 0 <= float(self.confidence) <= 1:
            raise ValueError("confidence must be between 0 and 1")

    @property
    def score_pair(self):
        if self.top_right_score is None or self.bottom_left_score is None:
            return None
        return self.top_right_score, self.bottom_left_score


@dataclass(frozen=True)
class PublicStateObservation:
    """Consensus result after target-room invariants are applied."""

    top_right_score: int | None
    bottom_left_score: int | None
    hand_number: int | None
    remaining_tiles: int | None
    score_votes: int
    hand_votes: int
    remaining_votes: int
    issues: tuple[str, ...] = ()
    safe_for_executor: bool = False

    @property
    def score_pair(self):
        if self.top_right_score is None or self.bottom_left_score is None:
            return None
        return self.top_right_score, self.bottom_left_score

    @property
    def valid(self):
        return not self.issues


def _mode_with_votes(values):
    values = tuple(values)
    if not values:
        return None, 0
    counts = Counter(values)
    value, votes = counts.most_common(1)[0]
    return value, votes


def _candidate_score_is_physical(candidate):
    pair = candidate.score_pair
    if pair is None:
        return False
    left, right = pair
    return (
        0 <= left <= MATCH_TOTAL_SCORE
        and 0 <= right <= MATCH_TOTAL_SCORE
        and left + right == MATCH_TOTAL_SCORE
    )


def fuse_public_state(
    candidates,
    *,
    previous=None,
    expected_scores=None,
    minimum_votes=2,
    minimum_confidence=0.0,
):
    """Fuse several nearby frame reads into one conservative PublicState.

    Invalid single-frame score pairs are discarded *before* voting. An accepted
    score pair must conserve 2000. The optional expected_scores should be the
    engine's score pair in the same UI slot order; a mismatch is surfaced rather
    than silently overwriting the ledger.
    """
    if isinstance(minimum_votes, bool) or not isinstance(minimum_votes, Integral):
        raise ValueError("minimum_votes must be an integer")
    if minimum_votes < 1:
        raise ValueError("minimum_votes must be >= 1")
    if not 0 <= minimum_confidence <= 1:
        raise ValueError("minimum_confidence must be between 0 and 1")
    if previous is not None and not isinstance(previous, PublicStateObservation):
        raise TypeError("previous must be PublicStateObservation or None")
    if expected_scores is not None:
        try:
            expected_scores = tuple(expected_scores)
        except TypeError as exc:
            raise ValueError("expected_scores must contain two integers") from exc
        if (
            len(expected_scores) != 2
            or any(
                isinstance(value, bool) or not isinstance(value, Integral)
                for value in expected_scores
            )
            or sum(expected_scores) != MATCH_TOTAL_SCORE
        ):
            raise ValueError("expected_scores must be a zero-sum 2000-point pair")

    candidates = tuple(
        candidate
        for candidate in candidates
        if isinstance(candidate, PublicStateCandidate)
        and candidate.confidence >= minimum_confidence
    )

    score_pair, score_votes = _mode_with_votes(
        candidate.score_pair
        for candidate in candidates
        if _candidate_score_is_physical(candidate)
    )
    hand_number, hand_votes = _mode_with_votes(
        candidate.hand_number
        for candidate in candidates
        if candidate.hand_number is not None
        and 1 <= candidate.hand_number <= MATCH_HAND_COUNT
    )
    remaining_tiles, remaining_votes = _mode_with_votes(
        candidate.remaining_tiles
        for candidate in candidates
        if candidate.remaining_tiles is not None
        and 0 <= candidate.remaining_tiles <= 144
    )

    issues = []
    if score_votes < minimum_votes:
        score_pair = None
        if any(candidate.score_pair is not None for candidate in candidates):
            issues.append("score_consensus")
    if hand_votes < minimum_votes:
        hand_number = None
        if any(candidate.hand_number is not None for candidate in candidates):
            issues.append("hand_consensus")
    if remaining_votes < minimum_votes:
        remaining_tiles = None
        if any(candidate.remaining_tiles is not None for candidate in candidates):
            issues.append("remaining_consensus")

    if score_pair is not None and expected_scores is not None:
        if score_pair != expected_scores:
            issues.append("engine_score_mismatch")

    if previous is not None:
        previous_hand = previous.hand_number
        if hand_number is not None and previous_hand is not None:
            if hand_number < previous_hand:
                issues.append("hand_regression")
            elif hand_number > previous_hand + 1:
                issues.append("hand_jump")

        same_hand = (
            hand_number is not None
            and previous_hand is not None
            and hand_number == previous_hand
        )
        if same_hand:
            if (
                score_pair is not None
                and previous.score_pair is not None
                and score_pair != previous.score_pair
            ):
                issues.append("score_changed_inside_hand")
            if (
                remaining_tiles is not None
                and previous.remaining_tiles is not None
                and remaining_tiles > previous.remaining_tiles
            ):
                issues.append("remaining_increased_inside_hand")

    if score_pair is None:
        top_right_score = bottom_left_score = None
    else:
        top_right_score, bottom_left_score = score_pair

    return PublicStateObservation(
        top_right_score=top_right_score,
        bottom_left_score=bottom_left_score,
        hand_number=hand_number,
        remaining_tiles=remaining_tiles,
        score_votes=score_votes,
        hand_votes=hand_votes,
        remaining_votes=remaining_votes,
        issues=tuple(dict.fromkeys(issues)),
        safe_for_executor=False,
    )
