"""Decision-intervention diagnostics for experimental PublicRolloutAgent V0.14.

This benchmark is diagnostic, not a promotion gate. It runs full eight-hand
ordinary-real matches while collecting only information already available to
the live V0.14 agent. It never inspects opponent concealed tiles or future wall
order.

Example:
    python -B -m workspace.simulator.rollout_diagnostics \
        --pairs 5 --seed-start 400200
"""
import argparse
from collections import Counter
from dataclasses import asdict
import json

from workspace.ai import MeldAwareShantenAgent, PublicRolloutAgent
from .match_runner import run_real_ordinary_match


def _v010_factory(seed=None):
    return MeldAwareShantenAgent(seed=seed, template_samples=32)


def _mean(values):
    values = tuple(values)
    return sum(values) / len(values) if values else None


def _bucket_margin(value):
    if value is None:
        return "no_match_context"
    if value > 0:
        return "leading"
    if value < 0:
        return "trailing"
    return "tied"


def summarize_rollout_diagnostics(records, *, attempts):
    """Summarize captured V0.14 diagnostics from completed diagnostic matches."""
    records = tuple(records)
    attempts = tuple(attempts)
    gate_counts = Counter(record["diagnostic"].gate for record in records)
    searched = tuple(
        record for record in records
        if record["diagnostic"].gate in (
            "searched_same_as_v010", "searched_intervention")
    )
    interventions = tuple(
        record for record in searched
        if record["diagnostic"].changed_from_v010
    )

    searched_by_shanten = Counter(
        str(record["diagnostic"].min_shanten) for record in searched
    )
    interventions_by_shanten = Counter(
        str(record["diagnostic"].min_shanten) for record in interventions
    )
    interventions_by_hand = Counter(
        str(record["diagnostic"].hand_index) for record in interventions
    )
    interventions_by_margin = Counter(
        _bucket_margin(record["diagnostic"].score_margin_for_actor)
        for record in interventions
    )

    live_deltas = tuple(
        record["diagnostic"].immediate_live_delta
        for record in interventions
        if record["diagnostic"].immediate_live_delta is not None
    )
    type_deltas = tuple(
        record["diagnostic"].immediate_type_delta
        for record in interventions
        if record["diagnostic"].immediate_type_delta is not None
    )
    total_requested = sum(
        record["diagnostic"].rollout_samples_requested for record in searched
    )
    total_completed = sum(
        record["diagnostic"].rollout_samples_completed for record in searched
    )
    total_cutoffs = sum(
        record["diagnostic"].special_cutoffs for record in searched
    )
    candidate_counts = tuple(
        record["diagnostic"].candidate_count for record in searched
    )

    completed_attempts = tuple(
        attempt for attempt in attempts if attempt["status"] == "COMPLETED"
    )
    match_score_deltas = tuple(
        attempt["v014_score_delta"] for attempt in completed_attempts
    )
    deal_in_deltas = tuple(
        attempt["v014_deal_in_delta"] for attempt in completed_attempts
    )
    unknown_reasons = Counter()
    for attempt in attempts:
        unknown_reasons.update(attempt["unresolved"])

    intervention_examples = []
    for record in interventions[:80]:
        item = asdict(record["diagnostic"])
        item["seed"] = record["seed"]
        item["swapped"] = record["swapped"]
        intervention_examples.append(item)

    return {
        "attempts": len(attempts),
        "completed_attempts": len(completed_attempts),
        "stopped_attempts": len(attempts) - len(completed_attempts),
        "unknown_reasons": dict(sorted(unknown_reasons.items())),
        "mean_v014_score_delta_per_match": _mean(match_score_deltas),
        "mean_v014_deal_in_delta_per_match": _mean(deal_in_deltas),
        "multi_discard_decisions": len(records),
        "gate_counts": dict(sorted(gate_counts.items())),
        "searched_decisions": len(searched),
        "interventions": len(interventions),
        "intervention_rate_among_searched": (
            len(interventions) / len(searched) if searched else 0.0
        ),
        "intervention_rate_among_multi_discard": (
            len(interventions) / len(records) if records else 0.0
        ),
        "searched_by_shanten": dict(sorted(searched_by_shanten.items())),
        "interventions_by_shanten": dict(
            sorted(interventions_by_shanten.items())),
        "interventions_by_hand_index": dict(
            sorted(interventions_by_hand.items())),
        "interventions_by_match_margin": dict(
            sorted(interventions_by_margin.items())),
        "mean_immediate_live_delta_on_intervention": _mean(live_deltas),
        "mean_immediate_type_delta_on_intervention": _mean(type_deltas),
        "interventions_sacrificing_immediate_live": sum(
            value < 0 for value in live_deltas),
        "interventions_preserving_immediate_live": sum(
            value == 0 for value in live_deltas),
        "interventions_improving_immediate_live": sum(
            value > 0 for value in live_deltas),
        "average_candidate_count_when_searched": _mean(candidate_counts),
        "rollout_samples_requested": total_requested,
        "rollout_samples_completed": total_completed,
        "special_cutoffs": total_cutoffs,
        "special_cutoff_rate": (
            total_cutoffs / total_requested if total_requested else 0.0
        ),
        "intervention_examples": intervention_examples,
    }


def run_rollout_diagnostics(*, pairs=5, seed_start=400200, max_steps=1000):
    """Run paired seat orders while capturing V0.14's own audit records."""
    if type(pairs) is not int or pairs <= 0:
        raise ValueError("pairs must be a positive integer")
    if type(seed_start) is not int:
        raise ValueError("seed_start must be an integer")
    if type(max_steps) is not int or max_steps <= 0:
        raise ValueError("max_steps must be a positive integer")

    records = []
    attempts = []
    for seed in range(seed_start, seed_start + pairs):
        for swapped in (False, True):
            agents_created = []

            def v014_factory(seed=None):
                agent = PublicRolloutAgent(
                    seed=seed,
                    template_samples=32,
                    rollout_samples=24,
                    own_draws=2,
                    candidate_limit=4,
                )
                agents_created.append(agent)
                return agent

            factories = (
                (v014_factory, _v010_factory)
                if not swapped else
                (_v010_factory, v014_factory)
            )
            seed_keys = (0, 1) if not swapped else (1, 0)
            result = run_real_ordinary_match(
                seed=seed,
                agent_factories=factories,
                max_steps=max_steps,
                agent_seed_keys=seed_keys,
            )
            v014_seat = 0 if not swapped else 1
            if result.complete:
                score_delta = (
                    result.final_scores[v014_seat]
                    - result.final_scores[1 - v014_seat]
                )
                deal_in_delta = (
                    result.deal_in_count_for(v014_seat)
                    - result.deal_in_count_for(1 - v014_seat)
                )
            else:
                score_delta = None
                deal_in_delta = None
            attempts.append({
                "seed": seed,
                "swapped": swapped,
                "status": result.status,
                "v014_score_delta": score_delta,
                "v014_deal_in_delta": deal_in_delta,
                "settled_hands": result.progress.hand_index,
                "unresolved": list(result.unresolved),
            })
            for agent in agents_created:
                for diagnostic in agent.diagnostics:
                    records.append({
                        "seed": seed,
                        "swapped": swapped,
                        "diagnostic": diagnostic,
                    })

    summary = summarize_rollout_diagnostics(records, attempts=attempts)
    summary["pairs"] = pairs
    summary["seed_start"] = seed_start
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=5)
    parser.add_argument("--seed-start", type=int, default=400200)
    parser.add_argument("--max-steps", type=int, default=1000)
    args = parser.parse_args(argv)
    report = run_rollout_diagnostics(
        pairs=args.pairs,
        seed_start=args.seed_start,
        max_steps=args.max_steps,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
