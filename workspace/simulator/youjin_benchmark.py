"""Paired V0.15b direct-Youjin vs V0.10 real-scored match pilot."""
import argparse
import json

from workspace.ai import DirectYoujinAgent, MeldAwareShantenAgent
from .match_evaluation import run_paired_real_matches
from .match_runner import run_real_youjin_match


def v010_factory(seed=None):
    return MeldAwareShantenAgent(seed=seed, template_samples=32)


def v015b_factory(seed=None):
    return DirectYoujinAgent(seed=seed, template_samples=32)


def run_youjin_pilot(*, pairs=5, seed_start=440000, max_steps=1000):
    if type(pairs) is not int or pairs <= 0:
        raise ValueError("pairs must be a positive integer")
    if type(seed_start) is not int:
        raise ValueError("seed_start must be an integer")
    return run_paired_real_matches(
        range(seed_start, seed_start + pairs),
        agent_factories=(v015b_factory, v010_factory),
        agent_names=("DirectYoujinAgent V0.15b candidate",
                     "MeldAwareShantenAgent V0.10"),
        max_steps=max_steps,
        match_runner=run_real_youjin_match,
    )


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=5)
    parser.add_argument("--seed-start", type=int, default=440000)
    parser.add_argument("--max-steps", type=int, default=1000)
    args = parser.parse_args(argv)
    report = run_youjin_pilot(
        pairs=args.pairs,
        seed_start=args.seed_start,
        max_steps=args.max_steps,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
