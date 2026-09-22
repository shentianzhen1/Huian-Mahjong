"""Deterministic paired evaluation for real-scored eight-hand matches.

This module is intentionally separate from hand-level simulation summaries.
Comparative metrics use only seed pairs where both original and seat-swapped
eight-hand matches complete, so incomplete/UNKNOWN pairs are never imputed.
"""
from collections import Counter
from dataclasses import asdict, dataclass
from math import sqrt

from huian.rules import DEFAULT_RULE_SNAPSHOT
from huian.version import PROJECT_VERSION
from workspace.ai import CurrentAgent, ShantenAgent, CURRENT_AGENT_VERSION
from .match_runner import run_real_ordinary_match, run_real_youjin_match


@dataclass(frozen=True)
class MatchAttemptSummary:
    pair_index: int
    seed: int
    swapped: bool
    status: str
    seat_scores: tuple[int, int]
    agent_scores: tuple[int, int] | None
    deal_ins_by_agent: tuple[int, int] | None
    settled_hands: int
    unresolved: tuple[str, ...]
    win_source_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class PairedMatchEvaluation:
    project_version: str
    rule_snapshot_id: str
    rule_snapshot_label: str
    agent_names: tuple[str, str]
    agent_versions: tuple[str | None, str | None]
    total_pairs: int
    completed_pairs: int
    incomplete_pairs: int
    completed_matches: int
    stopped_matches: int
    match_wins_by_agent: dict[str, int]
    ties: int
    average_final_score_by_agent: dict[str, float | None]
    average_score_delta_a_minus_b: float | None
    paired_score_delta_mean: float | None
    paired_score_delta_sd: float | None
    paired_score_delta_se: float | None
    paired_score_delta_ci95_low: float | None
    paired_score_delta_ci95_high: float | None
    paired_deal_in_delta_mean: float | None
    deal_ins_by_agent: dict[str, int]
    average_deal_ins_per_match_by_agent: dict[str, float | None]
    win_source_counts: dict[str, int]
    unknown_reasons: dict[str, int]
    per_match: tuple[MatchAttemptSummary, ...]

    def to_dict(self):
        return asdict(self)


def _sample_sd(values):
    values = tuple(values)
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    return sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))

def _factory_name(factory):
    name = getattr(factory, "__name__", None)
    if isinstance(name, str) and name:
        return name
    return type(factory).__name__


def _factory_version(factory):
    if factory is CurrentAgent:
        return CURRENT_AGENT_VERSION
    if factory is ShantenAgent:
        return "v0.3"
    return None


def run_paired_real_matches(
        seeds=range(20), *, agent_factories, agent_names=None, agent_versions=None,
        max_steps=1000, initial_dealer=0, match_runner=None):
    """Run original+swapped eight-hand matches and summarize complete pairs.

    Identity A is agent_factories[0] and identity B is agent_factories[1].
    A/B follow the factory across seats. For the real ordinary runner, each
    agent identity also keeps the same per-hand RNG seed across seat swaps;
    swapping seats must not silently change a stochastic policy's sample stream.
    Score/deal-in comparison excludes an entire seed pair unless both seat
    orders complete.
    """
    seeds = tuple(seeds)
    if not seeds or any(type(seed) is not int for seed in seeds):
        raise ValueError("seeds must be a nonempty iterable of integers")
    factories = tuple(agent_factories)
    if len(factories) != 2 or not all(callable(factory) for factory in factories):
        raise ValueError("Two callable agent factories are required")
    if type(max_steps) is not int or max_steps <= 0:
        raise ValueError("max_steps must be a positive integer")
    if type(initial_dealer) is not int or initial_dealer not in (0, 1):
        raise ValueError("initial_dealer must be seat 0 or 1")
    using_default_runner = match_runner is None
    if using_default_runner:
        match_runner = run_real_ordinary_match
    if not callable(match_runner):
        raise ValueError("match_runner must be callable")
    if agent_names is None:
        names = tuple(_factory_name(factory) for factory in factories)
    else:
        names = tuple(agent_names)
        if (len(names) != 2
                or any(not isinstance(name, str) or not name for name in names)):
            raise ValueError("agent_names must contain two nonempty strings")
    if agent_versions is None:
        versions = tuple(_factory_version(factory) for factory in factories)
    else:
        versions = tuple(agent_versions)
        if (len(versions) != 2
                or any(version is not None
                       and (not isinstance(version, str) or not version)
                       for version in versions)):
            raise ValueError("agent_versions must contain two nonempty strings or None")

    attempts = []
    pair_attempts = {}
    completed_matches = stopped_matches = 0
    unknown_reasons = Counter()

    for pair_index, seed in enumerate(seeds):
        pair_attempts[pair_index] = {}
        for swapped in (False, True):
            seat_factories = factories if not swapped else factories[::-1]
            if (using_default_runner
                    or match_runner in (run_real_ordinary_match,
                                        run_real_youjin_match)):
                seed_keys = (0, 1) if not swapped else (1, 0)
                result = match_runner(
                    seed=seed, agent_factories=seat_factories,
                    max_steps=max_steps, initial_dealer=initial_dealer,
                    agent_seed_keys=seed_keys)
            else:
                result = match_runner(
                    seed=seed, agent_factories=seat_factories,
                    max_steps=max_steps, initial_dealer=initial_dealer)
            status = result.status
            if status not in ("COMPLETED", "STOPPED_UNKNOWN"):
                raise ValueError(f"Unsupported match status: {status}")
            seat_scores = tuple(result.final_scores)
            if len(seat_scores) != 2 or any(type(value) is not int for value in seat_scores):
                raise ValueError("final_scores must be two integers")
            if result.complete:
                completed_matches += 1
                a_seat, b_seat = ((0, 1) if not swapped else (1, 0))
                agent_scores = (seat_scores[a_seat], seat_scores[b_seat])
                deal_ins = (
                    result.deal_in_count_for(a_seat),
                    result.deal_in_count_for(b_seat),
                )
                sources = tuple(sorted(result.win_source_counts.items()))
            else:
                stopped_matches += 1
                unknown_reasons.update(set(result.unresolved))
                agent_scores = None
                deal_ins = None
                sources = ()
            summary = MatchAttemptSummary(
                pair_index=pair_index, seed=seed, swapped=swapped,
                status=status, seat_scores=seat_scores,
                agent_scores=agent_scores, deal_ins_by_agent=deal_ins,
                settled_hands=result.progress.hand_index,
                unresolved=tuple(result.unresolved),
                win_source_counts=sources,
            )
            attempts.append(summary)
            pair_attempts[pair_index][swapped] = summary

    wins = {"A": 0, "B": 0}
    ties = 0
    score_sums = [0, 0]
    deal_in_sums = [0, 0]
    source_counts = Counter()
    completed_pairs = 0
    pair_score_deltas = []
    pair_deal_in_deltas = []

    for pair_index in sorted(pair_attempts):
        pair = pair_attempts[pair_index]
        if set(pair) != {False, True}:
            raise ValueError(f"Pair {pair_index} requires both seat orders")
        first, swapped = pair[False], pair[True]
        if not (first.status == "COMPLETED" and swapped.status == "COMPLETED"):
            continue
        completed_pairs += 1
        local_score_deltas = []
        local_deal_in_deltas = []
        for attempt in (first, swapped):
            a_score, b_score = attempt.agent_scores
            score_sums[0] += a_score
            score_sums[1] += b_score
            deal_in_sums[0] += attempt.deal_ins_by_agent[0]
            deal_in_sums[1] += attempt.deal_ins_by_agent[1]
            local_score_deltas.append(a_score - b_score)
            local_deal_in_deltas.append(
                attempt.deal_ins_by_agent[0] - attempt.deal_ins_by_agent[1]
            )
            source_counts.update(dict(attempt.win_source_counts))
            if a_score > b_score:
                wins["A"] += 1
            elif b_score > a_score:
                wins["B"] += 1
            else:
                ties += 1
        pair_score_deltas.append(sum(local_score_deltas) / 2)
        pair_deal_in_deltas.append(sum(local_deal_in_deltas) / 2)

    samples = 2 * completed_pairs
    avg_scores = {
        "A": score_sums[0] / samples if samples else None,
        "B": score_sums[1] / samples if samples else None,
    }
    avg_deal_ins = {
        "A": deal_in_sums[0] / samples if samples else None,
        "B": deal_in_sums[1] / samples if samples else None,
    }
    delta = (
        (score_sums[0] - score_sums[1]) / samples
        if samples else None
    )
    pair_delta_mean = (
        sum(pair_score_deltas) / len(pair_score_deltas)
        if pair_score_deltas else None
    )
    pair_delta_sd = _sample_sd(pair_score_deltas)
    pair_delta_se = (
        pair_delta_sd / sqrt(len(pair_score_deltas))
        if pair_delta_sd is not None and pair_score_deltas else None
    )
    ci95_low = (
        pair_delta_mean - 1.96 * pair_delta_se
        if pair_delta_mean is not None and pair_delta_se is not None else None
    )
    ci95_high = (
        pair_delta_mean + 1.96 * pair_delta_se
        if pair_delta_mean is not None and pair_delta_se is not None else None
    )
    pair_deal_in_delta_mean = (
        sum(pair_deal_in_deltas) / len(pair_deal_in_deltas)
        if pair_deal_in_deltas else None
    )
    return PairedMatchEvaluation(
        project_version=PROJECT_VERSION,
        rule_snapshot_id=DEFAULT_RULE_SNAPSHOT.fingerprint,
        rule_snapshot_label=DEFAULT_RULE_SNAPSHOT.label,
        agent_names=names,
        agent_versions=versions,
        total_pairs=len(seeds),
        completed_pairs=completed_pairs,
        incomplete_pairs=len(seeds) - completed_pairs,
        completed_matches=completed_matches,
        stopped_matches=stopped_matches,
        match_wins_by_agent=wins,
        ties=ties,
        average_final_score_by_agent=avg_scores,
        average_score_delta_a_minus_b=delta,
        paired_score_delta_mean=pair_delta_mean,
        paired_score_delta_sd=pair_delta_sd,
        paired_score_delta_se=pair_delta_se,
        paired_score_delta_ci95_low=ci95_low,
        paired_score_delta_ci95_high=ci95_high,
        paired_deal_in_delta_mean=pair_deal_in_delta_mean,
        deal_ins_by_agent={"A": deal_in_sums[0], "B": deal_in_sums[1]},
        average_deal_ins_per_match_by_agent=avg_deal_ins,
        win_source_counts=dict(sorted(source_counts.items())),
        unknown_reasons=dict(sorted(unknown_reasons.items())),
        per_match=tuple(attempts),
    )
