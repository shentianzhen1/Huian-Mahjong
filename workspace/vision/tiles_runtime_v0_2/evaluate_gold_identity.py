"""Leakage-aware evaluation for the Gold-normalized identity bank.

Every approved base-tile crop can be projected through Gold normalization.
Labels marked gold_skin_only contribute only to this domain and never to the
ordinary concealed classifier. Evaluation holds out one logical source session
at a time and therefore cannot score a class that exists only in the held-out
session.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path

from workspace.vision.tiles_v0_1.evaluate_tiles import (
    _crop_label,
    _group_key,
    summarize_predictions,
)
from workspace.vision.tiles_v0_1.labels import approved_labels
from workspace.vision.tiles_v0_1.taxonomy import HONORS, SUITED, category_for
from workspace.vision.tiles_v0_1.template_classifier import TemplateTileClassifier


GOLD_SOURCE_REGIONS = frozenset({"hand_region", "draw_region", "draw_visual", "gold_region"})
STANDARD_CLASSES = frozenset(SUITED) | frozenset(HONORS)


def _runtime_gate_fields(prediction, train_labels, *, confidence_threshold: float) -> dict:
    train_classes = {row["tile_id"] for row in train_labels}
    predicted_category = category_for(prediction.tile_id)
    category_complete = not any(
        category_for(tile_id) == predicted_category
        for tile_id in STANDARD_CLASSES - train_classes
    )
    supporting_groups = {
        _group_key(row)
        for row in train_labels
        if row["tile_id"] == prediction.tile_id
    }
    multi_session = len(supporting_groups) >= 2
    accepted = bool(
        prediction.confidence >= confidence_threshold
        and category_complete
        and multi_session
    )
    if prediction.confidence < confidence_threshold:
        reason = "below_confidence_threshold"
    elif not category_complete:
        reason = "category_has_missing_standard_class"
    elif not multi_session:
        reason = "class_not_cross_session_validated_in_gold_identity"
    else:
        reason = "accepted"
    return {
        "runtime_gate_accepted": accepted,
        "runtime_gate_reason": reason,
        "runtime_supporting_groups": len(supporting_groups),
    }


def evaluate_gold_identity(
    dataset_root: str | Path = "dataset/tiles_runtime_v0_2",
    *,
    confidence_threshold: float = 0.82,
) -> dict:
    if isinstance(confidence_threshold, bool) or not isinstance(
        confidence_threshold, (int, float)
    ):
        raise ValueError("confidence_threshold must be numeric")
    if not 0 <= confidence_threshold <= 1:
        raise ValueError("confidence_threshold must be between 0 and 1")

    root = Path(dataset_root)
    labels = [
        row for row in approved_labels(root)
        if row["region"] in GOLD_SOURCE_REGIONS
    ]
    if not labels:
        raise ValueError("No approved Gold-identity source labels")

    groups: dict[str, list[dict]] = defaultdict(list)
    for row in labels:
        groups[_group_key(row)].append(row)
    if len(groups) < 2:
        raise ValueError("Need at least two source sessions for holdout evaluation")

    rows = []
    unscorable = []
    for held_out, test_labels in sorted(groups.items()):
        train_labels = tuple(
            row for row in labels if _group_key(row) != held_out
        )
        train_classes = {row["tile_id"] for row in train_labels}
        if not train_classes:
            continue
        classifier = TemplateTileClassifier.from_labels(root, train_labels)

        for label in test_labels:
            true_tile = label["tile_id"]
            if true_tile not in train_classes:
                unscorable.append({
                    "group": held_out,
                    "image": label["image"],
                    "tile_id": true_tile,
                    "gold_skin_only": bool(label.get("gold_skin_only")),
                    "reason": "true_class_missing_outside_holdout_group_in_gold_identity",
                })
                continue
            prediction = classifier.classify_gold_skin(_crop_label(root, label))
            row = {
                "group": held_out,
                "image": label["image"],
                "region": "gold_identity",
                "source_region": label["region"],
                "gold_skin_only": bool(label.get("gold_skin_only")),
                "true_tile": true_tile,
                "predicted_tile": prediction.tile_id,
                "confidence": prediction.confidence,
                "correct": prediction.tile_id == true_tile,
                "true_category": category_for(true_tile),
                "predicted_category": category_for(prediction.tile_id),
                "category_correct": (
                    category_for(prediction.tile_id) == category_for(true_tile)
                ),
            }
            row.update(_runtime_gate_fields(
                prediction,
                train_labels,
                confidence_threshold=float(confidence_threshold),
            ))
            rows.append(row)

    report = summarize_predictions(
        rows,
        total_labels=len(labels),
        confidence_threshold=float(confidence_threshold),
    )
    gold_rows = [row for row in rows if row["gold_skin_only"]]
    gold_accepted = [row for row in gold_rows if row["runtime_gate_accepted"]]
    report.update({
        "schema_version": "vision_runtime_v0_2_gold_identity_eval_v0_1",
        "method": "leave_logical_source_session_out_gold_normalized_identity",
        "template_scope": "gold_identity",
        "distinct_source_groups": len(groups),
        "runtime_gate": {
            "accepted_labels": sum(row["runtime_gate_accepted"] for row in rows),
            "accepted_accuracy": (
                sum(row["correct"] for row in rows if row["runtime_gate_accepted"])
                / sum(row["runtime_gate_accepted"] for row in rows)
                if any(row["runtime_gate_accepted"] for row in rows)
                else None
            ),
            "rejection_reasons": {
                reason: sum(row["runtime_gate_reason"] == reason for row in rows)
                for reason in sorted({row["runtime_gate_reason"] for row in rows})
            },
        },
        "gold_skin_only_subset": {
            "scorable_labels": len(gold_rows),
            "correct": sum(row["correct"] for row in gold_rows),
            "accepted_labels": len(gold_accepted),
            "accepted_correct": sum(row["correct"] for row in gold_accepted),
        },
        "unscorable": unscorable,
        "rows": rows,
    })
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="dataset/tiles_runtime_v0_2")
    parser.add_argument("--confidence", type=float, default=0.82)
    parser.add_argument("--output")
    args = parser.parse_args()
    report = evaluate_gold_identity(
        args.dataset,
        confidence_threshold=args.confidence,
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
