"""Fast single-hand smoke for Youjin meld-deficit shadow diagnostics.

Both seats use GoldYoujinShadowAgent, which always executes the promoted V0.10
action. This maximizes diagnostic coverage without changing play policy and is
much cheaper than running full eight-hand matches.
"""
import argparse
from collections import Counter
import json

from workspace.ai import GoldYoujinShadowAgent
from .core import Simulator


def _mean(values):
    values = tuple(values)
    return sum(values) / len(values) if values else None


def run_youjin_deficit_hand_smoke(
        *, hands=8, seed_start=430000, max_steps=1000):
    if type(hands) is not int or hands <= 0:
        raise ValueError("hands must be a positive integer")
    if type(seed_start) is not int:
        raise ValueError("seed_start must be an integer")
    if type(max_steps) is not int or max_steps <= 0:
        raise ValueError("max_steps must be a positive integer")

    simulator = Simulator()
    records = []
    statuses = Counter()
    unknown = Counter()

    for seed in range(seed_start, seed_start + hands):
        agents = (
            GoldYoujinShadowAgent(seed=seed * 2, template_samples=32),
            GoldYoujinShadowAgent(seed=seed * 2 + 1, template_samples=32),
        )
        result = simulator.run_normal_hand(
            seed=seed,
            agents=agents,
            max_steps=max_steps,
        )
        statuses[result.status] += 1
        unknown.update(result.unresolved)
        for seat, agent in enumerate(agents):
            for diagnostic in agent.gold_diagnostics:
                records.append((seed, seat, diagnostic))

    multi = tuple(
        item for item in records
        if item[2].min_shanten_frontier_size > 1
    )
    differentiated = tuple(
        item for item in multi if item[2].signal_differentiated
    )
    changes = tuple(
        item for item in differentiated if item[2].would_change_v010
    )

    deficit_deltas = tuple(
        item[2].meld_deficit_delta
        for item in changes
        if item[2].meld_deficit_delta is not None
    )
    live_deltas = tuple(item[2].immediate_live_delta for item in changes)
    type_deltas = tuple(item[2].immediate_type_delta for item in changes)

    examples = []
    for seed, seat, item in changes[:60]:
        examples.append({
            "seed": seed,
            "seat": seat,
            "shanten": item.shanten,
            "baseline_tile": item.baseline_tile,
            "structural_choice_tile": item.structural_choice_tile,
            "baseline_meld_deficit": item.baseline_meld_deficit,
            "best_meld_deficit": item.best_meld_deficit,
            "meld_deficit_delta": item.meld_deficit_delta,
            "immediate_live_delta": item.immediate_live_delta,
            "immediate_type_delta": item.immediate_type_delta,
            "future_live_delta": item.future_live_delta,
            "future_type_delta": item.future_type_delta,
        })

    return {
        "hands_requested": hands,
        "seed_start": seed_start,
        "status_counts": dict(sorted(statuses.items())),
        "unknown_reasons": dict(sorted(unknown.items())),
        "gold_discard_decisions": len(records),
        "multi_candidate_min_shanten_decisions": len(multi),
        "signal_differentiated_frontiers": len(differentiated),
        "shadow_would_change_v010": len(changes),
        "shadow_change_rate_among_gold_decisions": (
            len(changes) / len(records) if records else 0.0
        ),
        "shadow_change_rate_among_multi_frontiers": (
            len(changes) / len(multi) if multi else 0.0
        ),
        "mean_meld_deficit_delta_on_change": _mean(deficit_deltas),
        "changes_reducing_meld_deficit": sum(
            value < 0 for value in deficit_deltas
        ),
        "mean_immediate_live_delta_on_change": _mean(live_deltas),
        "mean_immediate_type_delta_on_change": _mean(type_deltas),
        "changes_losing_live_copies": sum(value < 0 for value in live_deltas),
        "changes_losing_effective_types": sum(value < 0 for value in type_deltas),
        "changes_with_live_loss_at_most_one": sum(value >= -1 for value in live_deltas),
        "changes_with_no_type_loss": sum(value >= 0 for value in type_deltas),
        "candidate_examples": examples,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--hands", type=int, default=8)
    parser.add_argument("--seed-start", type=int, default=430000)
    parser.add_argument("--max-steps", type=int, default=1000)
    args = parser.parse_args(argv)
    report = run_youjin_deficit_hand_smoke(
        hands=args.hands,
        seed_start=args.seed_start,
        max_steps=args.max_steps,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
