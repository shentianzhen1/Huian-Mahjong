"""Paired V0.10 vs V0.6 evaluation with confirmed Youjin scoring enabled."""
import argparse
import json

from workspace.ai import CurrentAgent, TenpaiRiskTieBreakAgent
from .match_evaluation import run_paired_real_matches
from .match_runner import run_real_youjin_match


def run_youjin_ab(*, pairs=5, seed_start=440000, max_steps=1000):
    if type(pairs) is not int or pairs <= 0:
        raise ValueError("pairs must be a positive integer")
    if type(seed_start) is not int:
        raise ValueError("seed_start must be an integer")
    result = run_paired_real_matches(
        range(seed_start, seed_start + pairs),
        agent_factories=(CurrentAgent, TenpaiRiskTieBreakAgent),
        agent_names=("CurrentAgent V0.10", "TenpaiRiskTieBreakAgent V0.6"),
        max_steps=max_steps,
        match_runner=run_real_youjin_match,
    )
    return result.to_dict()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=5)
    parser.add_argument("--seed-start", type=int, default=440000)
    parser.add_argument("--max-steps", type=int, default=1000)
    args = parser.parse_args(argv)
    print(json.dumps(run_youjin_ab(
        pairs=args.pairs,
        seed_start=args.seed_start,
        max_steps=args.max_steps,
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
