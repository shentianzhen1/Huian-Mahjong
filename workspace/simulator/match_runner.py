"""Eight-hand match orchestration over real settled hand outcomes.

The runner owns match-level state only: scores, dealer, repeat-dealer count and
current dealer base. A supplied hand_runner owns one Mahjong hand and must
return a settled zero-sum result or explicitly stop as UNKNOWN.

This keeps the 8-hand objective real without pretending unresolved special
settlements are known.
"""
from dataclasses import dataclass
from numbers import Integral

from huian.rules import UnknownRuleError
from .match import MatchProgressState


def _seat_or_none(value, name):
    if value is not None and (type(value) is not int or value not in (0, 1)):
        raise ValueError(f"{name} must be seat 0, seat 1 or None")


@dataclass(frozen=True)
class MatchHandContext:
    hand_index: int
    dealer: int
    current_dealer_base: int
    scores: tuple[int, int]
    hands_remaining: int


@dataclass(frozen=True)
class MatchHandResult:
    """One hand result returned to MatchRunner.

    status is SETTLED or STOPPED_UNKNOWN. SETTLED results carry real zero-sum
    rewards and an optional winner (None means draw). STOPPED_UNKNOWN carries
    rule ids and never mutates the match ledger.
    """

    status: str
    rewards: tuple[int, int] = (0, 0)
    winner: int | None = None
    terminal_reason: str | None = None
    unresolved: tuple[str, ...] = ()

    def __post_init__(self):
        if self.status not in ("SETTLED", "STOPPED_UNKNOWN"):
            raise ValueError("hand result status must be SETTLED or STOPPED_UNKNOWN")
        if (not isinstance(self.rewards, tuple) or len(self.rewards) != 2
                or any(isinstance(v, bool) or not isinstance(v, Integral)
                       for v in self.rewards)):
            raise ValueError("hand rewards must be a two-integer tuple")
        if sum(self.rewards) != 0:
            raise ValueError("hand rewards must be zero-sum")
        _seat_or_none(self.winner, "winner")
        if self.status == "SETTLED":
            if self.unresolved:
                raise ValueError("settled hand cannot carry unresolved rules")
        else:
            if not self.unresolved:
                raise ValueError("STOPPED_UNKNOWN requires unresolved rule ids")
            if self.rewards != (0, 0) or self.winner is not None:
                raise ValueError("unknown hand cannot mutate scores or declare a winner")

    @classmethod
    def settled(cls, rewards, *, winner, terminal_reason=None):
        return cls("SETTLED", tuple(rewards), winner, terminal_reason, ())

    @classmethod
    def unknown(cls, *rule_ids):
        if not rule_ids:
            raise ValueError("unknown result requires at least one rule id")
        return cls("STOPPED_UNKNOWN", unresolved=tuple(rule_ids))


@dataclass(frozen=True)
class MatchHandRecord:
    context: MatchHandContext
    result: MatchHandResult
    scores_after: tuple[int, int] | None
    dealer_after: int | None
    next_dealer_base: int | None


@dataclass(frozen=True)
class MatchRunResult:
    status: str
    progress: MatchProgressState
    hands: tuple[MatchHandRecord, ...]
    unresolved: tuple[str, ...] = ()
    stopped_hand_index: int | None = None

    @property
    def final_scores(self):
        return self.progress.scores

    @property
    def complete(self):
        return self.status == "COMPLETED"


class MatchRunner:
    """Run up to eight hands while preserving evidence-safe UNKNOWN stops."""

    def __init__(self, hand_runner):
        if not callable(hand_runner):
            raise TypeError("hand_runner must be callable")
        self.hand_runner = hand_runner

    @staticmethod
    def _context(progress):
        return MatchHandContext(
            hand_index=progress.hand_index,
            dealer=progress.dealer,
            current_dealer_base=progress.current_dealer_base,
            scores=progress.scores,
            hands_remaining=progress.hands_remaining,
        )

    def run(self, *, initial_dealer=0):
        progress = MatchProgressState.initial(initial_dealer)
        records = []
        while not progress.complete:
            context = self._context(progress)
            try:
                result = self.hand_runner(context)
            except UnknownRuleError as exc:
                result = MatchHandResult.unknown(*exc.rule_ids)
            if not isinstance(result, MatchHandResult):
                raise TypeError("hand_runner must return MatchHandResult")
            if result.status == "STOPPED_UNKNOWN":
                records.append(MatchHandRecord(
                    context, result, None, None, None
                ))
                return MatchRunResult(
                    "STOPPED_UNKNOWN", progress, tuple(records),
                    unresolved=result.unresolved,
                    stopped_hand_index=context.hand_index,
                )

            progress = progress.apply_settled_hand(
                result.rewards, winner=result.winner
            )
            next_base = None if progress.complete else progress.current_dealer_base
            records.append(MatchHandRecord(
                context, result, progress.scores, progress.dealer, next_base
            ))

        return MatchRunResult("COMPLETED", progress, tuple(records))


def run_eight_hand_match(hand_runner, *, initial_dealer=0):
    """Convenience entry point for the default fixed eight-hand room."""
    return MatchRunner(hand_runner).run(initial_dealer=initial_dealer)
