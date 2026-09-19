"""Evaluate temporal gold-tile recognition on replay ROI crops.

This is deliberately NOT a cross-session generalization metric. It measures
whether one reviewed gold seed per replay session can recognize the remaining
gold frames from that same session after Huian gold-skin normalization.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from PIL import Image

from .labels import approved_labels
from .template_classifier import TemplateTileClassifier


def _read_jsonl(path):
    if not path.exists():
        return ()
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return tuple(rows)


def _gold_seed_truth(labels):
    truth = {}
    seeds = []
    for label in labels:
        if label.get("status") != "approved":
            continue
        if label.get("region") != "gold_region":
            continue
        session = label.get("source_session")
        if not session:
            continue
        previous = truth.get(session)
        if previous is not None and previous != label["tile_id"]:
            raise ValueError(
                f"Conflicting gold labels for {session}: "
                f"{previous} vs {label['tile_id']}"
            )
        truth[session] = label["tile_id"]
        seeds.append(label)
    return truth, tuple(seeds)


def evaluate_gold_temporal(dataset_root, *, confidence_threshold=0.75):
    root = Path(dataset_root)
    labels = approved_labels(root)
    truth_by_session, gold_seeds = _gold_seed_truth(labels)
    if not gold_seeds:
        raise ValueError("No approved gold_region labels with source_session")
    if not 0 <= confidence_threshold <= 1:
        raise ValueError("confidence_threshold must be between 0 and 1")

    frame_rows = _read_jsonl(root / "meta" / "frames.jsonl")
    frame_to_session = {
        row["image"]: row.get("source")
        for row in frame_rows
        if row.get("image") and row.get("source")
    }
    roi_rows = _read_jsonl(root / "meta" / "roi_crops.jsonl")

    classifier = TemplateTileClassifier.from_labels(root, gold_seeds)
    predictions = []
    for row in roi_rows:
        if row.get("region") != "gold_region":
            continue
        session = frame_to_session.get(row.get("source_image"))
        if session not in truth_by_session:
            continue
        image_path = root / row["image"]
        if not image_path.exists():
            continue
        with Image.open(image_path) as source:
            prediction = classifier.classify(
                source.convert("RGB"), region="gold_region"
            )
        truth = truth_by_session[session]
        predictions.append({
            "session": session,
            "image": row["image"],
            "true_tile": truth,
            "predicted_tile": prediction.tile_id,
            "confidence": prediction.confidence,
            "correct": prediction.tile_id == truth,
        })

    per_session = {}
    grouped = defaultdict(list)
    for row in predictions:
        grouped[row["session"]].append(row)

    majority_correct = 0
    for session, rows in sorted(grouped.items()):
        counts = Counter(row["predicted_tile"] for row in rows)
        majority_tile, majority_count = counts.most_common(1)[0]
        accepted = [
            row for row in rows
            if row["confidence"] >= confidence_threshold
        ]
        accepted_correct = sum(row["correct"] for row in accepted)
        true_tile = truth_by_session[session]
        majority_is_correct = majority_tile == true_tile
        majority_correct += int(majority_is_correct)
        per_session[session] = {
            "true_tile": true_tile,
            "frames": len(rows),
            "correct_frames": sum(row["correct"] for row in rows),
            "frame_accuracy": (
                sum(row["correct"] for row in rows) / len(rows)
            ),
            "majority_tile": majority_tile,
            "majority_count": majority_count,
            "majority_correct": majority_is_correct,
            "accepted_frames": len(accepted),
            "accepted_accuracy": (
                accepted_correct / len(accepted) if accepted else None
            ),
        }

    total = len(predictions)
    correct = sum(row["correct"] for row in predictions)
    accepted = [
        row for row in predictions
        if row["confidence"] >= confidence_threshold
    ]
    accepted_correct = sum(row["correct"] for row in accepted)

    return {
        "metric_scope": (
            "same-session temporal consistency; not cross-session "
            "gold-class generalization"
        ),
        "gold_seed_classes": sorted({
            label["tile_id"] for label in gold_seeds
        }),
        "gold_seed_sessions": sorted(truth_by_session),
        "frames": total,
        "frame_accuracy": correct / total if total else None,
        "confidence_threshold": confidence_threshold,
        "accepted_frames": len(accepted),
        "accepted_fraction": len(accepted) / total if total else 0.0,
        "accepted_accuracy": (
            accepted_correct / len(accepted) if accepted else None
        ),
        "session_majority_correct": majority_correct,
        "session_count": len(per_session),
        "session_majority_accuracy": (
            majority_correct / len(per_session) if per_session else None
        ),
        "per_session": per_session,
        "predictions": predictions,
        "safe_for_executor": False,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate Huian replay gold-tile temporal recognition")
    parser.add_argument("--dataset", default="dataset/tiles_v0_1")
    parser.add_argument("--confidence", type=float, default=0.75)
    parser.add_argument("--output")
    args = parser.parse_args()
    report = evaluate_gold_temporal(
        args.dataset, confidence_threshold=args.confidence
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
