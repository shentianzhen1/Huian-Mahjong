"""Batch/multi-timepoint evaluation for Huian PublicState V0.1.

A manifest supplies ground truth plus one or more nearby frame paths for each
stable timepoint.  The evaluator reports raw single-frame OCR/status accuracy
separately from short-window fused PublicState accuracy.

Ground truth is never injected into the reader.  Optional engine_expected_scores
may be supplied when the benchmark intentionally evaluates the same
MatchScoreState cross-check available in production.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from PIL import Image

from .public_state_reader import PublicStateReader


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def _metric_summary(total, readable, correct):
    return {
        "total": total,
        "readable": readable,
        "correct": correct,
        "coverage": _ratio(readable, total),
        "accuracy_when_readable": _ratio(correct, readable),
        "exact_rate": _ratio(correct, total),
    }


def _truth(sample):
    source = sample.get("truth", sample)
    hand = source.get("hand_number", source.get("hand"))
    top = source.get("top_right_score")
    bottom = source.get("bottom_left_score")
    remaining = source.get("remaining_tiles")
    values = {
        "hand_number": hand,
        "top_right_score": top,
        "bottom_left_score": bottom,
        "remaining_tiles": remaining,
    }
    if any(isinstance(value, bool) or not isinstance(value, int)
           for value in values.values()):
        raise ValueError("truth requires integer hand/score/remaining fields")
    if not 1 <= hand <= 8:
        raise ValueError("truth hand_number must be 1..8")
    if top < 0 or bottom < 0 or top + bottom != 2000:
        raise ValueError("truth scores must be nonnegative and sum to 2000")
    if not 0 <= remaining <= 144:
        raise ValueError("truth remaining_tiles must be 0..144")
    return values


def _frame_paths(sample):
    if "frames" in sample:
        frames = sample["frames"]
    elif "frame" in sample:
        frames = [sample["frame"]]
    else:
        raise ValueError("each sample requires frame or frames")
    if (not isinstance(frames, list) or not frames
            or any(not isinstance(item, str) or not item for item in frames)):
        raise ValueError("frames must be a non-empty list of paths")
    return tuple(frames)


def load_public_state_manifest(path):
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    samples = payload.get("samples") if isinstance(payload, dict) else payload
    if not isinstance(samples, list) or not samples:
        raise ValueError("manifest must contain a non-empty samples list")
    normalized = []
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            raise ValueError("each sample must be an object")
        item = dict(sample)
        item["_index"] = index
        item["_truth"] = _truth(sample)
        item["_frames"] = _frame_paths(sample)
        normalized.append(item)
    return tuple(normalized)


def _resolve_frame(path_text, *, manifest_path, frames_root=None):
    path = Path(path_text)
    if path.is_absolute():
        return path
    if frames_root is not None:
        return Path(frames_root) / path
    return Path(manifest_path).resolve().parent / path


def evaluate_public_state_manifest(
        manifest_path, *, frames_root=None, reader=None, minimum_votes=2):
    """Evaluate all manifest timepoints in order.

    Previous-state transition inference is carried forward only from a fused
    observation that has no issues and has both a score pair and hand number.
    This mirrors the conservative "trusted previous" intent of the live reader.
    """
    if isinstance(minimum_votes, bool) or not isinstance(minimum_votes, int):
        raise ValueError("minimum_votes must be an integer")
    if minimum_votes < 1:
        raise ValueError("minimum_votes must be >= 1")

    manifest_path = Path(manifest_path)
    samples = load_public_state_manifest(manifest_path)
    reader = reader or PublicStateReader()

    raw_total = 0
    raw_score_readable = raw_score_correct = 0
    raw_hand_readable = raw_hand_correct = 0
    raw_remaining_readable = raw_remaining_correct = 0
    raw_complete_correct = 0

    fused_total = len(samples)
    fused_score_readable = fused_score_correct = 0
    fused_hand_readable = fused_hand_correct = 0
    fused_remaining_readable = fused_remaining_correct = 0
    fused_complete_readable = fused_complete_correct = 0

    frame_issue_counts = Counter()
    fused_issue_counts = Counter()
    score_mode_counts = Counter()
    remaining_mode_counts = Counter()
    rows = []
    previous = None

    for sample in samples:
        truth = sample["_truth"]
        image_paths = tuple(
            _resolve_frame(
                item,
                manifest_path=manifest_path,
                frames_root=frames_root,
            )
            for item in sample["_frames"]
        )
        images = []
        try:
            for path in image_paths:
                with Image.open(path) as image:
                    images.append(image.convert("RGB"))
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"missing PublicState benchmark frame: {exc.filename}"
            ) from exc

        expected_scores = sample.get("engine_expected_scores")
        if expected_scores is not None:
            if (not isinstance(expected_scores, list)
                    or len(expected_scores) != 2
                    or any(isinstance(value, bool) or not isinstance(value, int)
                           for value in expected_scores)
                    or sum(expected_scores) != 2000):
                raise ValueError(
                    "engine_expected_scores must be two integers summing to 2000"
                )

        window = reader.read_window(
            images,
            previous=previous,
            expected_scores=expected_scores,
            minimum_votes=minimum_votes,
        )

        raw_frames = []
        for frame_index, frame in enumerate(window.frames):
            raw_total += 1
            score = frame.score.score_pair
            hand = frame.status.hand_number
            remaining = frame.status.remaining_tiles
            truth_score = (
                truth["top_right_score"], truth["bottom_left_score"]
            )

            if score is not None:
                raw_score_readable += 1
                if tuple(score) == truth_score:
                    raw_score_correct += 1
            if hand is not None:
                raw_hand_readable += 1
                if hand == truth["hand_number"]:
                    raw_hand_correct += 1
            if remaining is not None:
                raw_remaining_readable += 1
                if remaining == truth["remaining_tiles"]:
                    raw_remaining_correct += 1
            if (
                score is not None
                and hand is not None
                and remaining is not None
                and tuple(score) == truth_score
                and hand == truth["hand_number"]
                and remaining == truth["remaining_tiles"]
            ):
                raw_complete_correct += 1

            score_mode_counts[frame.score.mode] += 1
            remaining_mode = getattr(frame.status, "remaining_mode", "primary")
            remaining_mode_counts[remaining_mode] += 1
            frame_issue_counts.update(frame.issues)
            raw_frames.append({
                "frame": str(image_paths[frame_index]),
                "score_pair": list(score) if score is not None else None,
                "hand_number": hand,
                "remaining_tiles": remaining,
                "score_mode": frame.score.mode,
                "remaining_mode": remaining_mode,
                "raw_remaining": getattr(frame.status, "raw_remaining", None),
                "raw_remaining_fallback": getattr(
                    frame.status, "raw_remaining_fallback", None
                ),
                "raw_hand_progress": getattr(
                    frame.status, "raw_hand_progress", None
                ),
                "issues": list(frame.issues),
            })

        observation = window.observation
        score = observation.score_pair
        hand = observation.hand_number
        remaining = observation.remaining_tiles
        truth_score = (
            truth["top_right_score"], truth["bottom_left_score"]
        )

        if score is not None:
            fused_score_readable += 1
            if tuple(score) == truth_score:
                fused_score_correct += 1
        if hand is not None:
            fused_hand_readable += 1
            if hand == truth["hand_number"]:
                fused_hand_correct += 1
        if remaining is not None:
            fused_remaining_readable += 1
            if remaining == truth["remaining_tiles"]:
                fused_remaining_correct += 1

        complete_readable = (
            score is not None and hand is not None and remaining is not None
        )
        if complete_readable:
            fused_complete_readable += 1
            if (
                tuple(score) == truth_score
                and hand == truth["hand_number"]
                and remaining == truth["remaining_tiles"]
            ):
                fused_complete_correct += 1

        fused_issue_counts.update(observation.issues)
        rows.append({
            "sample_id": sample.get(
                "id", sample.get("video", f"sample_{sample['_index']:03d}")
            ),
            "truth": truth,
            "raw_frames": raw_frames,
            "fused": {
                "score_pair": list(score) if score is not None else None,
                "hand_number": hand,
                "remaining_tiles": remaining,
                "score_votes": observation.score_votes,
                "hand_votes": observation.hand_votes,
                "remaining_votes": observation.remaining_votes,
                "issues": list(observation.issues),
                "safe_for_executor": observation.safe_for_executor,
            },
        })

        if (
            not observation.issues
            and observation.score_pair is not None
            and observation.hand_number is not None
        ):
            previous = observation

    return {
        "manifest": str(manifest_path),
        "timepoints": fused_total,
        "frames": raw_total,
        "minimum_votes": minimum_votes,
        "raw_frame": {
            "score_pair": _metric_summary(
                raw_total, raw_score_readable, raw_score_correct),
            "hand_number": _metric_summary(
                raw_total, raw_hand_readable, raw_hand_correct),
            "remaining_tiles": _metric_summary(
                raw_total, raw_remaining_readable, raw_remaining_correct),
            "complete_exact": {
                "total": raw_total,
                "correct": raw_complete_correct,
                "exact_rate": _ratio(raw_complete_correct, raw_total),
            },
            "score_mode_counts": dict(sorted(score_mode_counts.items())),
            "remaining_mode_counts": dict(sorted(remaining_mode_counts.items())),
            "issue_counts": dict(sorted(frame_issue_counts.items())),
        },
        "fused_window": {
            "score_pair": _metric_summary(
                fused_total, fused_score_readable, fused_score_correct),
            "hand_number": _metric_summary(
                fused_total, fused_hand_readable, fused_hand_correct),
            "remaining_tiles": _metric_summary(
                fused_total, fused_remaining_readable,
                fused_remaining_correct),
            "complete_state": _metric_summary(
                fused_total, fused_complete_readable, fused_complete_correct),
            "issue_counts": dict(sorted(fused_issue_counts.items())),
        },
        "safe_for_executor": False,
        "samples": rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("--frames-root")
    parser.add_argument("--minimum-votes", type=int, default=2)
    parser.add_argument("--output")
    args = parser.parse_args(argv)

    report = evaluate_public_state_manifest(
        args.manifest,
        frames_root=args.frames_root,
        minimum_votes=args.minimum_votes,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
