"""Shadow benchmark for confirmed Jin / Youjin structural opportunity.

The shadow agent always returns the promoted V0.10 action. Diagnostics compare
the full minimum-shanten discard frontier and ask whether a discard with a
smaller confirmed Youjin meld deficit would have been available, together with
the immediate ordinary live/type cost of that hypothetical choice.

Example:
    python -B -m workspace.simulator.gold_youjin_shadow \
        --pairs 5 --seed-start 410000
"""
import argparse
from collections import Counter
from dataclasses import asdict
import json

from workspace.ai import GoldYoujinShadowAgent, MeldAwareShantenAgent
from .match_runner import run_real_ordinary_match


def _v010_factory(seed=None):
    return MeldAwareShantenAgent(seed=seed, template_samples=32)


def _mean(values):
    values = tuple(values)
    return sum(values) / len(values) if values else None


def _margin_bucket(value):
    if value is None:
        return "no_match_context"
    if value > 0:
        return "leading"
    if value < 0:
        return "trailing"
    return "tied"


def summarize_gold_youjin_shadow(records, *, attempts):
    records = tuple(records)
    attempts = tuple(attempts)
    frontier_multi = tuple(
        record for record in records
        if record["diagnostic"].min_shanten_frontier_size > 1
    )
    differentiated = tuple(
        record for record in frontier_multi
        if record["diagnostic"].signal_differentiated
    )
    changes = tuple(
        record for record in differentiated
        if record["diagnostic"].would_change_v010
    )

    by_gold = Counter(
        str(record["diagnostic"].gold_count) for record in records
    )
    frontier_by_shanten = Counter(
        str(record["diagnostic"].shanten) for record in frontier_multi
    )
    changes_by_shanten = Counter(
        str(record["diagnostic"].shanten) for record in changes
    )
    changes_by_margin = Counter(
        _margin_bucket(record["diagnostic"].score_margin_for_actor)
        for record in changes
    )

    future_live_deltas = tuple(
        record["diagnostic"].future_live_delta for record in changes
    )
    future_type_deltas = tuple(
        record["diagnostic"].future_type_delta for record in changes
    )
    deficit_deltas = tuple(
        record["diagnostic"].meld_deficit_delta for record in changes
        if record["diagnostic"].meld_deficit_delta is not None
    )
    immediate_live_deltas = tuple(
        record["diagnostic"].immediate_live_delta for record in changes
    )
    immediate_type_deltas = tuple(
        record["diagnostic"].immediate_type_delta for record in changes
    )

    completed_attempts = tuple(
        attempt for attempt in attempts if attempt["status"] == "COMPLETED"
    )
    unknown_reasons = Counter()
    for attempt in attempts:
        unknown_reasons.update(attempt["unresolved"])

    examples = []
    for record in changes[:80]:
        payload = asdict(record["diagnostic"])
        payload["seed"] = record["seed"]
        payload["swapped"] = record["swapped"]
        examples.append(payload)

    return {
        "attempts": len(attempts),
        "completed_attempts": len(completed_attempts),
        "stopped_attempts": len(attempts) - len(completed_attempts),
        "unknown_reasons": dict(sorted(unknown_reasons.items())),
        "gold_discard_decisions": len(records),
        "gold_decisions_by_gold_count": dict(sorted(by_gold.items())),
        "multi_candidate_min_shanten_decisions": len(frontier_multi),
        "signal_differentiated_frontiers": len(differentiated),
        "shadow_would_change_v010": len(changes),
        "shadow_change_rate_among_gold_decisions": (
            len(changes) / len(records) if records else 0.0
        ),
        "shadow_change_rate_among_multi_frontiers": (
            len(changes) / len(frontier_multi) if frontier_multi else 0.0
        ),
        "baseline_immediate_youjin_entries": sum(
            record["diagnostic"].baseline_immediate_entry for record in records
        ),
        "best_immediate_youjin_entries": sum(
            record["diagnostic"].best_immediate_entry for record in records
        ),
        "frontiers_by_shanten": dict(sorted(frontier_by_shanten.items())),
        "changes_by_shanten": dict(sorted(changes_by_shanten.items())),
        "changes_by_match_margin": dict(sorted(changes_by_margin.items())),
        "mean_future_youjin_live_delta_on_change": _mean(future_live_deltas),
        "mean_future_youjin_type_delta_on_change": _mean(future_type_deltas),
        "mean_meld_deficit_delta_on_change": _mean(deficit_deltas),
        "changes_reducing_meld_deficit": sum(
            value < 0 for value in deficit_deltas
        ),
        "mean_immediate_live_delta_on_change": _mean(immediate_live_deltas),
        "mean_immediate_type_delta_on_change": _mean(immediate_type_deltas),
        "changes_losing_live_copies": sum(
            value < 0 for value in immediate_live_deltas
        ),
        "changes_losing_effective_types": sum(
            value < 0 for value in immediate_type_deltas
        ),
        "changes_improving_future_youjin_live": sum(
            value > 0 for value in future_live_deltas
        ),
        "changes_equal_future_youjin_live": sum(
            value == 0 for value in future_live_deltas
        ),
        "shadow_change_examples": examples,
    }


def run_gold_youjin_shadow(*, pairs=5, seed_start=410000, max_steps=1000):
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

            def shadow_factory(seed=None):
                agent = GoldYoujinShadowAgent(
                    seed=seed, template_samples=32)
                agents_created.append(agent)
                return agent

            factories = (
                (shadow_factory, _v010_factory)
                if not swapped else
                (_v010_factory, shadow_factory)
            )
            seed_keys = (0, 1) if not swapped else (1, 0)
            result = run_real_ordinary_match(
                seed=seed,
                agent_factories=factories,
                max_steps=max_steps,
                agent_seed_keys=seed_keys,
            )
            attempts.append({
                "seed": seed,
                "swapped": swapped,
                "status": result.status,
                "settled_hands": result.progress.hand_index,
                "unresolved": list(result.unresolved),
            })
            for agent in agents_created:
                for diagnostic in agent.gold_diagnostics:
                    records.append({
                        "seed": seed,
                        "swapped": swapped,
                        "diagnostic": diagnostic,
                    })

    summary = summarize_gold_youjin_shadow(records, attempts=attempts)
    summary["pairs"] = pairs
    summary["seed_start"] = seed_start
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=5)
    parser.add_argument("--seed-start", type=int, default=410000)
    parser.add_argument("--max-steps", type=int, default=1000)
    args = parser.parse_args(argv)
    report = run_gold_youjin_shadow(
        pairs=args.pairs,
        seed_start=args.seed_start,
        max_steps=args.max_steps,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
