"""Decision diagnostics for constrained Gold/Youjin V0.15 candidate."""
from collections import Counter
import argparse
import json

from workspace.ai import ConstrainedGoldYoujinAgent, MeldAwareShantenAgent
from .match_runner import run_real_ordinary_match


def _v010_factory(seed=None):
    return MeldAwareShantenAgent(seed=seed, template_samples=32)


def _mean(values):
    values = tuple(values)
    return sum(values) / len(values) if values else None


def run_v015_diagnostics(*, pairs=1, seed_start=420000, max_steps=1000):
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
            created = []

            def candidate_factory(seed=None):
                agent = ConstrainedGoldYoujinAgent(
                    seed=seed, template_samples=32,
                    max_live_loss=1,
                    min_future_live_gain=4,
                    min_future_type_gain=1,
                )
                created.append(agent)
                return agent

            factories = (
                (candidate_factory, _v010_factory)
                if not swapped else
                (_v010_factory, candidate_factory)
            )
            seed_keys = (0, 1) if not swapped else (1, 0)
            result = run_real_ordinary_match(
                seed=seed,
                agent_factories=factories,
                max_steps=max_steps,
                agent_seed_keys=seed_keys,
            )
            seat = 0 if not swapped else 1
            score_delta = (
                result.final_scores[seat] - result.final_scores[1 - seat]
                if result.complete else None
            )
            deal_in_delta = (
                result.deal_in_count_for(seat)
                - result.deal_in_count_for(1 - seat)
                if result.complete else None
            )
            attempts.append({
                "seed": seed,
                "swapped": swapped,
                "status": result.status,
                "score_delta": score_delta,
                "deal_in_delta": deal_in_delta,
                "unresolved": list(result.unresolved),
            })
            for agent in created:
                records.extend(agent.v015_diagnostics)

    gates = Counter(item.reason_gate for item in records)
    interventions = tuple(item for item in records if item.changed_from_v010)
    score_deltas = tuple(
        item["score_delta"] for item in attempts if item["score_delta"] is not None
    )
    deal_deltas = tuple(
        item["deal_in_delta"] for item in attempts if item["deal_in_delta"] is not None
    )
    unknown = Counter()
    for item in attempts:
        unknown.update(item["unresolved"])

    wins = sum(value > 0 for value in score_deltas)
    losses = sum(value < 0 for value in score_deltas)
    ties = sum(value == 0 for value in score_deltas)
    return {
        "pairs": pairs,
        "evaluation_scope": (
            "ordinary-safety-only; Youjin special rewards are absent, so "
            "score/deal-in direction is diagnostic and not promotion evidence"
        ),
        "completed_attempts": len(score_deltas),
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "mean_score_delta": _mean(score_deltas),
        "mean_deal_in_delta": _mean(deal_deltas),
        "diagnosed_gold_decisions": len(records),
        "interventions": len(interventions),
        "intervention_rate": (
            len(interventions) / len(records) if records else 0.0
        ),
        "gate_counts": dict(sorted(gates.items())),
        "mean_immediate_live_delta": _mean(
            item.immediate_live_delta for item in interventions
        ),
        "mean_immediate_type_delta": _mean(
            item.immediate_type_delta for item in interventions
        ),
        "mean_future_live_delta": _mean(
            item.future_live_delta for item in interventions
        ),
        "mean_future_type_delta": _mean(
            item.future_type_delta for item in interventions
        ),
        "live_loss_minus_one": sum(
            item.immediate_live_delta == -1 for item in interventions
        ),
        "live_loss_zero": sum(
            item.immediate_live_delta == 0 for item in interventions
        ),
        "type_loss_violations": sum(
            item.immediate_type_delta < 0 for item in interventions
        ),
        "immediate_youjin_entry_interventions": sum(
            item.reason_gate == "immediate_youjin_entry"
            for item in interventions
        ),
        "future_youjin_gain_interventions": sum(
            item.reason_gate == "future_youjin_gain"
            for item in interventions
        ),
        "unknown_reasons": dict(sorted(unknown.items())),
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=1)
    parser.add_argument("--seed-start", type=int, default=420000)
    parser.add_argument("--max-steps", type=int, default=1000)
    args = parser.parse_args(argv)
    report = run_v015_diagnostics(
        pairs=args.pairs, seed_start=args.seed_start, max_steps=args.max_steps)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
