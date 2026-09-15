"""Reproduce and verify one hand from a saved offline evaluation."""
import argparse
from pathlib import Path

from .artifacts import replay_saved_hand, save_replay


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report_dir", type=Path)
    parser.add_argument("--hand-index", type=int, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.hand_index < 0:
        parser.error("--hand-index must be nonnegative")
    if args.output is not None and args.output.exists():
        parser.error("--output already exists; choose a new file")
    try:
        result = replay_saved_hand(args.report_dir, args.hand_index)
        if args.output is not None:
            save_replay(args.output, result)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    summary = result["summary"]
    print(f"Verified hand {args.hand_index}: {summary['status']}, "
          f"seed={summary['seed']}, swapped={summary['swapped']}, "
          f"steps={summary['steps']}")
    if args.output is not None:
        print(f"Trace: {args.output.resolve()}")


if __name__ == "__main__":
    main()
