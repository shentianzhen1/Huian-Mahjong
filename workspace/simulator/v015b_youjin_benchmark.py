"""Paired real-scoring V0.15b vs promoted V0.10 evaluation.

Uses the confirmed Youjin-family match profile. Qiangjin, Sanjindao,
Eight-Flower-You and unresolved Gang-Hu scopes remain outside this evaluator.
"""
import argparse
import json
import math
import statistics

from workspace.ai import MeldAwareShantenAgent, YoujinTenpaiCandidateAgent
from .match_runner import run_real_youjin_match


def _factory(cls):
    def make(seed=None):
        return cls(seed=seed, template_samples=32)
    return make


def _candidate_margin(result, candidate_seat):
    scores = result.final_scores
    return scores[candidate_seat] - scores[1 - candidate_seat]


def _ci95(values):
    values = tuple(values)
    if len(values) < 2:
        return None
    mean = statistics.mean(values)
    half = 1.96 * statistics.stdev(values) / math.sqrt(len(values))
    return [mean - half, mean + half]


def run_v015b_youjin_benchmark(*, pairs=10, seed_start=440000, max_steps=1000):
    if type(pairs) is not int or pairs <= 0:
        raise ValueError("pairs must be a positive integer")
    candidate = _factory(YoujinTenpaiCandidateAgent)
    baseline = _factory(MeldAwareShantenAgent)

    attempts = []
    pair_means = []
    candidate_wins = baseline_wins = ties = 0
    source_counts = {}

    for seed in range(seed_start, seed_start + pairs):
        margins = []
        for swapped in (False, True):
            factories = (baseline, candidate) if swapped else (candidate, baseline)
            candidate_seat = 1 if swapped else 0
            seed_keys = (1, 0) if swapped else (0, 1)
            result = run_real_youjin_match(
                seed=seed,
                agent_factories=factories,
                max_steps=max_steps,
                agent_seed_keys=seed_keys,
            )
            row = {
                "seed": seed,
                "swapped": swapped,
                "status": result.status,
                "unresolved": list(result.unresolved),
                "final_scores": list(result.final_scores),
                "win_source_counts": result.win_source_counts,
            }
            if result.complete:
                margin = _candidate_margin(result, candidate_seat)
                row["candidate_margin"] = margin
                margins.append(margin)
                if margin > 0:
                    candidate_wins += 1
                elif margin < 0:
                    baseline_wins += 1
                else:
                    ties += 1
                for source, count in result.win_source_counts.items():
                    source_counts[source] = source_counts.get(source, 0) + count
            attempts.append(row)
        if len(margins) == 2:
            pair_means.append(sum(margins) / 2)

    return {
        "pairs_requested": pairs,
        "seed_start": seed_start,
        "completed_matches": sum(row["status"] == "COMPLETED" for row in attempts),
        "stopped_matches": sum(row["status"] != "COMPLETED" for row in attempts),
        "candidate_wins": candidate_wins,
        "v010_wins": baseline_wins,
        "ties": ties,
        "complete_pairs": len(pair_means),
        "mean_candidate_margin_by_pair": (
            statistics.mean(pair_means) if pair_means else None
        ),
        "candidate_margin_95ci": _ci95(pair_means),
        "win_source_counts": dict(sorted(source_counts.items())),
        "attempts": attempts,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=10)
    parser.add_argument("--seed-start", type=int, default=440000)
    parser.add_argument("--max-steps", type=int, default=1000)
    args = parser.parse_args(argv)
    print(json.dumps(run_v015b_youjin_benchmark(
        pairs=args.pairs,
        seed_start=args.seed_start,
        max_steps=args.max_steps,
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
