"""Manual benchmark, outside default unit tests."""
import argparse
import json
from pathlib import Path
import sys

from .artifacts import AGENTS, run_saved_evaluation
from .evaluation import run_many_normal_hands


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--seed-offset", type=int, default=0)
    parser.add_argument("--max-steps", type=int, default=1000)
    parser.add_argument("--swap-seats", action="store_true")
    parser.add_argument("--agent-a", choices=sorted(AGENTS), default="random")
    parser.add_argument("--agent-b", choices=sorted(AGENTS), default="baseline")
    parser.add_argument("--dealer", type=int, choices=(0, 1), default=0)
    parser.add_argument("--output-dir", type=Path, help="Create a new report directory; never overwrite")
    parser.add_argument("--progress", action="store_true", help="Write per-hand progress to stderr")
    args = parser.parse_args(argv)
    if args.count <= 0:
        parser.error("--count must be positive")
    if args.max_steps <= 0:
        parser.error("--max-steps must be positive")

    def progress(done, total, summary):
        print(f"[{done}/{total}] seed={summary.seed} swapped={summary.swapped} "
              f"status={summary.status} steps={summary.steps}", file=sys.stderr, flush=True)

    seeds = range(args.seed_offset, args.seed_offset + args.count)
    total = args.count * (2 if args.swap_seats else 1)
    done = 0

    def on_hand(summary, result):
        nonlocal done
        done += 1
        progress(done, total, summary)

    try:
        if args.output_dir is not None:
            report = run_saved_evaluation(
                args.output_dir, seeds, agent_names=(args.agent_a, args.agent_b),
                max_steps=args.max_steps, swap_seats=args.swap_seats, dealer=args.dealer,
                on_progress=progress if args.progress else None)
        else:
            report = run_many_normal_hands(
                seeds, agent_factories=(AGENTS[args.agent_a], AGENTS[args.agent_b]),
                max_steps=args.max_steps, swap_seats=args.swap_seats, dealer=args.dealer,
                on_hand=on_hand if args.progress else None)
    except KeyboardInterrupt:
        print("Interrupted; flushed hand records remain in the report directory "
              "when --output-dir was supplied.", file=sys.stderr)
        return 130
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
