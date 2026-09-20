"""Ordinary-safety pilot for constrained Jin/Youjin V0.15 candidate.

IMPORTANT:
The current real-ordinary match runner does not execute/settle Youjin-family
special wins. Therefore match score is a downside/safety diagnostic only; it
must NOT be used as promotion evidence for V0.15.

The useful outputs here are intervention frequency and the immediate ordinary
offense cost paid by those interventions.
"""
import argparse
from collections import Counter
import json

from workspace.ai import ConstrainedGoldYoujinAgent, MeldAwareShantenAgent
from .match_evaluation import run_paired_real_matches


def v010_factory(seed=None):
    return MeldAwareShantenAgent(seed=seed, template_samples=32)


def run_v015_ordinary_safety(
        *, pairs=3, seed_start=420000, max_steps=1000,
        max_live_loss=1, min_future_live_gain=4, min_future_type_gain=1):
    if type(pairs) is not int or pairs <= 0:
        raise ValueError("pairs must be a positive integer")
    if type(seed_start) is not int:
        raise ValueError("seed_start must be an integer")

    created = []

    def v015_factory(seed=None):
        agent = ConstrainedGoldYoujinAgent(
            seed=seed,
            template_samples=32,
            max_live_loss=max_live_loss,
            min_future_live_gain=min_future_live_gain,
            min_future_type_gain=min_future_type_gain,
        )
        created.append(agent)
        return agent

    evaluation = run_paired_real_matches(
        range(seed_start, seed_start + pairs),
        agent_factories=(v015_factory, v010_factory),
        agent_names=(
            "ConstrainedGoldYoujinAgent V0.15 candidate",
            "MeldAwareShantenAgent V0.10",
        ),
        max_steps=max_steps,
    )

    diagnostics = tuple(
        record for agent in created for record in agent.v015_diagnostics
    )
    interventions = tuple(
        record for record in diagnostics if record.changed_from_v010
    )
    gates = Counter(record.reason_gate for record in diagnostics)
    by_shanten = Counter(str(record.shanten) for record in interventions)

    def mean(values):
        values = tuple(values)
        return sum(values) / len(values) if values else None

    report = evaluation.to_dict()
    report["evaluation_scope"] = (
        "ordinary-safety-only; Youjin special rewards are absent and match "
        "score is not promotion evidence"
    )
    report["v015_diagnostics"] = {
        "eligible_gold_decisions": len(diagnostics),
        "interventions": len(interventions),
        "intervention_rate": (
            len(interventions) / len(diagnostics) if diagnostics else 0.0
        ),
        "gate_counts": dict(sorted(gates.items())),
        "interventions_by_shanten": dict(sorted(by_shanten.items())),
        "mean_immediate_live_delta": mean(
            record.immediate_live_delta for record in interventions
        ),
        "mean_immediate_type_delta": mean(
            record.immediate_type_delta for record in interventions
        ),
        "mean_future_youjin_live_delta": mean(
            record.future_live_delta for record in interventions
        ),
        "mean_future_youjin_type_delta": mean(
            record.future_type_delta for record in interventions
        ),
        "live_loss_minus_one": sum(
            record.immediate_live_delta == -1 for record in interventions
        ),
        "live_loss_zero": sum(
            record.immediate_live_delta == 0 for record in interventions
        ),
        "type_loss_violations": sum(
            record.immediate_type_delta < 0 for record in interventions
        ),
        "immediate_youjin_entry_interventions": sum(
            record.reason_gate == "immediate_youjin_entry"
            for record in interventions
        ),
        "future_youjin_gain_interventions": sum(
            record.reason_gate == "future_youjin_gain"
            for record in interventions
        ),
    }
    return report


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=3)
    parser.add_argument("--seed-start", type=int, default=420000)
    parser.add_argument("--max-steps", type=int, default=1000)
    args = parser.parse_args(argv)
    report = run_v015_ordinary_safety(
        pairs=args.pairs,
        seed_start=args.seed_start,
        max_steps=args.max_steps,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
