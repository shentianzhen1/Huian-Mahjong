"""Paired V0.14-vs-V0.10 pilot benchmark.

Run from repository root:
    python -m workspace.simulator.rollout_benchmark --pairs 25 --seed-start 400000

This is intentionally a pilot harness. V0.14 must not be promoted from a pilot
alone; independent confirmation remains required.
"""
import argparse
import json

from workspace.ai import MeldAwareShantenAgent, PublicRolloutAgent
from .match_evaluation import run_paired_real_matches


def v010_factory(seed=None):
    return MeldAwareShantenAgent(seed=seed, template_samples=32)


def v014_factory(seed=None):
    return PublicRolloutAgent(
        seed=seed,
        template_samples=32,
        rollout_samples=24,
        own_draws=2,
        candidate_limit=4,
    )


def run_rollout_pilot(*, pairs=25, seed_start=400000, max_steps=1000):
    if type(pairs) is not int or pairs <= 0:
        raise ValueError("pairs must be a positive integer")
    if type(seed_start) is not int:
        raise ValueError("seed_start must be an integer")
    return run_paired_real_matches(
        range(seed_start, seed_start + pairs),
        agent_factories=(v014_factory, v010_factory),
        agent_names=("PublicRolloutAgent V0.14 candidate",
                     "MeldAwareShantenAgent V0.10"),
        max_steps=max_steps,
    )


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=25)
    parser.add_argument("--seed-start", type=int, default=400000)
    parser.add_argument("--max-steps", type=int, default=1000)
    args = parser.parse_args(argv)
    report = run_rollout_pilot(
        pairs=args.pairs,
        seed_start=args.seed_start,
        max_steps=args.max_steps,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
