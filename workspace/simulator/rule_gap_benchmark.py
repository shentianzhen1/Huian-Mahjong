"""Run swapped-seat real-ordinary eight-hand matches and print rule gaps.

This command never fills unresolved rules with guesses. It is intended to
prioritize evidence collection by showing which UNKNOWN rules stop the most
matches and preserving deterministic examples for each rule.
"""
import argparse
import json

from workspace.ai import BaselineAgent
from .core import RandomAgent
from .match_runner import run_real_ordinary_match
from .unknowns import summarize_match_rule_gaps


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=10,
                        help="Number of match seeds; each seed runs both seat orders")
    parser.add_argument("--seed-offset", type=int, default=0)
    parser.add_argument("--max-steps", type=int, default=1000)
    parser.add_argument("--max-examples", type=int, default=2,
                        help="Evidence examples retained per rule id")
    args = parser.parse_args(argv)

    if args.count <= 0:
        parser.error("--count must be positive")
    if args.max_steps <= 0:
        parser.error("--max-steps must be positive")
    if args.max_examples < 0:
        parser.error("--max-examples must be nonnegative")

    results = []
    for seed in range(args.seed_offset, args.seed_offset + args.count):
        for swapped in (False, True):
            factories = ((RandomAgent, BaselineAgent)
                         if not swapped else (BaselineAgent, RandomAgent))
            results.append(run_real_ordinary_match(
                seed=seed,
                agent_factories=factories,
                max_steps=args.max_steps,
            ))

    report = summarize_match_rule_gaps(
        results, max_examples_per_rule=args.max_examples)
    report["seed_offset"] = args.seed_offset
    report["seed_count"] = args.count
    report["seat_swapped"] = True
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
