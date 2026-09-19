"""Leakage-safe offline accuracy reporting for Tiles V0.1."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from PIL import Image

from .labels import approved_labels
from .taxonomy import category_for
from .template_classifier import TemplateTileClassifier


def _group_key(label):
    return str(label.get("source_frame") or label["image"])


def _crop_label(root, label):
    image_path = root / label["image"]
    if not image_path.exists():
        raise FileNotFoundError(image_path)
    with Image.open(image_path) as source:
        x, y, width, height = label["bbox"]
        if x < 0 or y < 0 or width <= 0 or height <= 0:
            raise ValueError("label bbox must have positive dimensions")
        if x + width > source.width or y + height > source.height:
            raise ValueError(f"label bbox exceeds image: {label['image']}")
        return source.convert("RGB").crop((x, y, x + width, y + height))


def summarize_predictions(rows, *, total_labels, confidence_threshold):
    scorable = len(rows)
    correct = sum(row["correct"] for row in rows)
    accepted = [row for row in rows if row["confidence"] >= confidence_threshold]
    accepted_correct = sum(row["correct"] for row in accepted)
    category_correct = sum(row["category_correct"] for row in rows)

    per_class = defaultdict(lambda: {
        "scorable": 0, "correct": 0, "accepted": 0, "accepted_correct": 0,
    })
    per_region = defaultdict(lambda: {"scorable": 0, "correct": 0})
    confusion = defaultdict(Counter)
    for row in rows:
        cls = per_class[row["true_tile"]]
        cls["scorable"] += 1
        cls["correct"] += int(row["correct"])
        if row["confidence"] >= confidence_threshold:
            cls["accepted"] += 1
            cls["accepted_correct"] += int(row["correct"])
        reg = per_region[row["region"]]
        reg["scorable"] += 1
        reg["correct"] += int(row["correct"])
        confusion[row["true_tile"]][row["predicted_tile"]] += 1

    for stats in per_class.values():
        stats["accuracy"] = (
            stats["correct"] / stats["scorable"] if stats["scorable"] else None
        )
        stats["accepted_accuracy"] = (
            stats["accepted_correct"] / stats["accepted"]
            if stats["accepted"] else None
        )
    for stats in per_region.values():
        stats["accuracy"] = (
            stats["correct"] / stats["scorable"] if stats["scorable"] else None
        )

    return {
        "total_approved_labels": total_labels,
        "scorable_labels": scorable,
        "unscorable_labels": total_labels - scorable,
        "scorable_coverage": scorable / total_labels if total_labels else 0.0,
        "exact_accuracy": correct / scorable if scorable else None,
        "category_accuracy": category_correct / scorable if scorable else None,
        "confidence_threshold": confidence_threshold,
        "accepted_labels": len(accepted),
        "accepted_fraction_of_scorable": (
            len(accepted) / scorable if scorable else 0.0
        ),
        "accepted_accuracy": (
            accepted_correct / len(accepted) if accepted else None
        ),
        "per_class": dict(sorted(per_class.items())),
        "per_region": dict(sorted(per_region.items())),
        "confusion": {
            truth: dict(sorted(pred.items()))
            for truth, pred in sorted(confusion.items())
        },
    }


def evaluate_template_dataset(dataset_root, *, confidence_threshold=0.80):
    """Leave one source-frame/image group out and report exact tile accuracy.

    A test label is scored only if its true tile class has at least one approved
    training example outside the held-out group. Missing cross-group class
    coverage is reported as unscorable instead of being hidden inside accuracy.
    """
    if isinstance(confidence_threshold, bool) or not isinstance(
            confidence_threshold, (int, float)):
        raise ValueError("confidence_threshold must be numeric")
    if not 0 <= confidence_threshold <= 1:
        raise ValueError("confidence_threshold must be between 0 and 1")

    root = Path(dataset_root)
    labels = approved_labels(root)
    if not labels:
        raise ValueError("No approved labels; accuracy cannot be measured")

    groups = defaultdict(list)
    for label in labels:
        groups[_group_key(label)].append(label)
    if len(groups) < 2:
        raise ValueError(
            "Need approved labels from at least two source frames/images "
            "for leakage-safe holdout evaluation"
        )

    rows = []
    unscorable = []
    all_labels = tuple(labels)
    for group_key, test_labels in sorted(groups.items()):
        train_labels = tuple(
            label for label in all_labels if _group_key(label) != group_key
        )
        train_classes = {label["tile_id"] for label in train_labels}
        eligible = [
            label for label in test_labels if label["tile_id"] in train_classes
        ]
        unscorable.extend(
            {
                "group": group_key,
                "image": label["image"],
                "tile_id": label["tile_id"],
                "region": label["region"],
                "reason": "true_class_missing_outside_holdout_group",
            }
            for label in test_labels if label["tile_id"] not in train_classes
        )
        if not eligible:
            continue
        classifier = TemplateTileClassifier.from_labels(root, train_labels)
        for label in eligible:
            prediction = classifier.classify(_crop_label(root, label))
            true_tile = label["tile_id"]
            predicted_tile = prediction.tile_id
            rows.append({
                "group": group_key,
                "image": label["image"],
                "region": label["region"],
                "true_tile": true_tile,
                "predicted_tile": predicted_tile,
                "confidence": prediction.confidence,
                "correct": predicted_tile == true_tile,
                "true_category": category_for(true_tile),
                "predicted_category": category_for(predicted_tile),
                "category_correct": (
                    category_for(predicted_tile) == category_for(true_tile)
                ),
            })

    report = summarize_predictions(
        rows,
        total_labels=len(labels),
        confidence_threshold=float(confidence_threshold),
    )
    report.update({
        "method": "leave_source_group_out",
        "distinct_source_groups": len(groups),
        "unscorable": unscorable,
        "predictions": rows,
        "safe_for_executor": False,
    })
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Leakage-safe Tiles V0.1 offline accuracy report")
    parser.add_argument("--dataset", default="dataset/tiles_v0_1")
    parser.add_argument("--confidence", type=float, default=0.80)
    parser.add_argument("--output")
    args = parser.parse_args()
    report = evaluate_template_dataset(
        args.dataset, confidence_threshold=args.confidence)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
