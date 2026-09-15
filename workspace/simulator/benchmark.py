"""Manual benchmark, outside default unit tests."""
import argparse
import json

from workspace.ai import BaselineAgent
from .core import RandomAgent
from .evaluation import run_many_normal_hands


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--seed-offset", type=int, default=0)
    parser.add_argument("--max-steps", type=int, default=1000)
    parser.add_argument("--swap-seats", action="store_true")
    args = parser.parse_args()
    if args.count <= 0:
        parser.error("--count must be positive")
    report = run_many_normal_hands(
        range(args.seed_offset, args.seed_offset + args.count),
        agent_factories=(RandomAgent, BaselineAgent),
        max_steps=args.max_steps, swap_seats=args.swap_seats,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
