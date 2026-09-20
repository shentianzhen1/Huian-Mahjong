"""Paired pilot for experimental constrained Gold/Youjin Agent V0.15."""
import argparse
import json

from workspace.ai import ConstrainedGoldYoujinAgent, MeldAwareShantenAgent
from .match_evaluation import run_paired_real_matches


def v010_factory(seed=None):
    return MeldAwareShantenAgent(seed=seed, template_samples=32)


def v015_factory(seed=None):
    return ConstrainedGoldYoujinAgent(
        seed=seed, template_samples=32,
        max_live_loss=1,
        min_future_live_gain=4,
        min_future_type_gain=1,
    )


def run_v015_pilot(*, pairs=1, seed_start=420000, max_steps=1000):
    if type(pairs) is not int or pairs <= 0:
        raise ValueError("pairs must be a positive integer")
    if type(seed_start) is not int:
        raise ValueError("seed_start must be an integer")
    return run_paired_real_matches(
        range(seed_start, seed_start + pairs),
        agent_factories=(v015_factory, v010_factory),
        agent_names=("ConstrainedGoldYoujinAgent V0.15 candidate",
                     "MeldAwareShantenAgent V0.10"),
        max_steps=max_steps,
    )


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=1)
    parser.add_argument("--seed-start", type=int, default=420000)
    parser.add_argument("--max-steps", type=int, default=1000)
    args = parser.parse_args(argv)
    report = run_v015_pilot(
        pairs=args.pairs, seed_start=args.seed_start, max_steps=args.max_steps)
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
