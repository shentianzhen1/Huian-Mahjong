"""Eight-hand match orchestration over real settled hand outcomes.

The runner owns match-level state only: scores, dealer, repeat-dealer count and
current dealer base. A supplied hand_runner owns one Mahjong hand and must
return a settled zero-sum result or explicitly stop as UNKNOWN.

This keeps the 8-hand objective real without pretending unresolved special
settlements are known.
"""
from copy import deepcopy
from dataclasses import dataclass
from numbers import Integral

from huian.rules import UnknownRuleError
from workspace.ai import MatchObservationContext
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
    consecutive_dealer_hands: int


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
    evidence: dict | None = None
    win_source: str | None = None

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
        if self.evidence is not None and not isinstance(self.evidence, dict):
            raise ValueError("hand evidence must be a dict or None")
        if self.status == "SETTLED":
            if self.unresolved:
                raise ValueError("settled hand cannot carry unresolved rules")
        else:
            if not self.unresolved:
                raise ValueError("STOPPED_UNKNOWN requires unresolved rule ids")
            if self.rewards != (0, 0) or self.winner is not None:
                raise ValueError("unknown hand cannot mutate scores or declare a winner")

    @classmethod
    def settled(cls, rewards, *, winner, terminal_reason=None, win_source=None):
        if win_source is not None and not isinstance(win_source, str):
            raise ValueError("win_source must be a string or None")
        return cls(
            "SETTLED", tuple(rewards), winner, terminal_reason, (), None,
            win_source
        )

    @classmethod
    def unknown(cls, *rule_ids, evidence=None):
        if not rule_ids:
            raise ValueError("unknown result requires at least one rule id")
        return cls(
            "STOPPED_UNKNOWN", unresolved=tuple(rule_ids), evidence=evidence
        )


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

    def deal_in_count_for(self, seat):
        """Count ordinary discard wins paid by seat in settled match hands."""
        if type(seat) is not int or seat not in (0, 1):
            raise ValueError("seat must be 0 or 1")
        return sum(
            1 for record in self.hands
            if record.result.status == "SETTLED"
            and record.result.win_source == "discard"
            and record.result.winner == 1 - seat
        )

    @property
    def win_source_counts(self):
        counts = {}
        for record in self.hands:
            source = record.result.win_source
            if record.result.status != "SETTLED" or source is None:
                continue
            counts[source] = counts.get(source, 0) + 1
        return counts

    @property
    def stopped_evidence(self):
        if self.status != "STOPPED_UNKNOWN" or not self.hands:
            return None
        return self.hands[-1].result.evidence


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
            consecutive_dealer_hands=progress.consecutive_dealer_hands,
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


def run_real_ordinary_match(seed=0, *, agent_factories=None, max_steps=1000,
                            initial_dealer=0, simulator=None,
                            agent_seed_keys=(0, 1)):
    """Run the eight-hand ordinary subset with real Pinghu/Zimo scoring.

    This is not yet the full target-room simulator: Qiangjin/Youjin/special wins
    remain outside this ordinary-subset runner. Every completed ordinary Hu uses
    FanAggregator + real Settlement. Rule UNKNOWN stops the match at that hand.
    Engineering limits/loops raise instead of being mislabeled as rule UNKNOWN.
    """
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if type(max_steps) is not int or max_steps <= 0:
        raise ValueError("max_steps must be a positive integer")
    if type(initial_dealer) is not int or initial_dealer not in (0, 1):
        raise ValueError("initial_dealer must be seat 0 or 1")
    agent_seed_keys = tuple(agent_seed_keys)
    if (len(agent_seed_keys) != 2
            or any(type(key) is not int or key not in (0, 1)
                   for key in agent_seed_keys)
            or set(agent_seed_keys) != {0, 1}):
        raise ValueError("agent_seed_keys must be a permutation of (0, 1)")

    from .core import RandomAgent, Simulator, SimulatorConfig
    factories = tuple(agent_factories) if agent_factories is not None else (
        RandomAgent, RandomAgent)
    if len(factories) != 2 or not all(callable(factory) for factory in factories):
        raise ValueError("Two callable agent factories are required")
    if simulator is None:
        simulator = Simulator(config=SimulatorConfig(enable_real_scoring=True))

    def run_hand(context):
        hand_seed = seed * 1000 + context.hand_index
        agents = tuple(
            factory(seed=hand_seed * 2 + agent_seed_keys[seat])
            for seat, factory in enumerate(factories)
        )
        observation_context = MatchObservationContext(
            scores=context.scores,
            hand_index=context.hand_index,
            hands_remaining=context.hands_remaining,
            dealer=context.dealer,
            current_dealer_base=context.current_dealer_base,
            consecutive_dealer_hands=context.consecutive_dealer_hands,
        )
        result = simulator.run_normal_hand(
            seed=hand_seed,
            agents=agents,
            max_steps=max_steps,
            dealer=context.dealer,
            current_dealer_base=context.current_dealer_base,
            match_context=observation_context,
        )
        if result.status == "COMPLETED":
            if not getattr(result, "real_scoring", False):
                raise ValueError("ordinary match requires real-scoring hand results")
            return MatchHandResult.settled(
                result.rewards,
                winner=result.winner,
                terminal_reason=result.terminal_reason,
                win_source=result.win_source,
            )
        if result.status == "STOPPED_UNKNOWN":
            evidence = deepcopy(result.unknown_evidence)
            if evidence is None:
                evidence = {}
            evidence["match_context"] = {
                "hand_index": context.hand_index,
                "dealer": context.dealer,
                "current_dealer_base": context.current_dealer_base,
                "scores": list(context.scores),
                "hands_remaining": context.hands_remaining,
                "consecutive_dealer_hands": context.consecutive_dealer_hands,
                "hand_seed": hand_seed,
            }
            return MatchHandResult.unknown(
                *result.unresolved, evidence=evidence
            )
        raise RuntimeError(
            f"ordinary hand did not settle safely: {result.status} "
            f"({result.stop_reason or 'no stop reason'})"
        )

    return MatchRunner(run_hand).run(initial_dealer=initial_dealer)
