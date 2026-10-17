"""Leakage-aware evaluation for a combined concealed hand/draw identity bank.

This module is diagnostic only. It does not change Runtime classification.
Hand and draw_visual use the same non-Gold face normalization, so this report
measures whether pooling those reviewed templates is a viable future runtime
domain.
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


CONCEALED_REGIONS = frozenset({"hand_region", "draw_region", "draw_visual"})
STANDARD_CLASSES = frozenset(SUITED) | frozenset(HONORS)


def _canonical_region(region: str) -> str:
    return "draw_visual" if region == "draw_region" else region


def _runtime_gate_fields(
    prediction,
    train_labels: tuple[dict, ...],
    *,
    confidence_threshold: float,
) -> dict:
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
        reason = "class_not_cross_session_validated_in_region"
    else:
        reason = "accepted"
    return {
        "runtime_gate_accepted": accepted,
        "runtime_gate_reason": reason,
        "runtime_supporting_groups": len(supporting_groups),
    }


def _runtime_gate_summary(rows: list[dict]) -> dict:
    accepted = [row for row in rows if row["runtime_gate_accepted"]]
    correct = sum(row["correct"] for row in accepted)
    return {
        "accepted_labels": len(accepted),
        "accepted_fraction_of_scorable": (
            len(accepted) / len(rows) if rows else 0.0
        ),
        "accepted_accuracy": (
            correct / len(accepted) if accepted else None
        ),
        "accepted_by_region": {
            region: sum(
                row["runtime_gate_accepted"] and row["region"] == region
                for row in rows
            )
            for region in sorted({row["region"] for row in rows})
        },
        "rejection_reasons": {
            reason: sum(
                row["runtime_gate_reason"] == reason
                for row in rows
            )
            for reason in sorted({row["runtime_gate_reason"] for row in rows})
        },
    }


def evaluate_concealed_identity(
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
        if (
            _canonical_region(row["region"]) in {"hand_region", "draw_visual"}
            and not row.get("gold_skin_only")
        )
    ]
    if not labels:
        raise ValueError("No approved concealed hand/draw labels")

    groups: dict[str, list[dict]] = defaultdict(list)
    for row in labels:
        groups[_group_key(row)].append(row)
    if len(groups) < 2:
        raise ValueError("Need at least two source sessions for holdout evaluation")

    rows = []
    unscorable = []
    all_labels = tuple(labels)
    for held_out, test_labels in sorted(groups.items()):
        train_labels = tuple(
            row for row in all_labels if _group_key(row) != held_out
        )
        train_classes = {row["tile_id"] for row in train_labels}
        if not train_classes:
            continue
        classifier = TemplateTileClassifier.from_labels(root, train_labels)

        for label in test_labels:
            if label["tile_id"] not in train_classes:
                unscorable.append({
                    "group": held_out,
                    "image": label["image"],
                    "tile_id": label["tile_id"],
                    "region": _canonical_region(label["region"]),
                    "reason": "true_class_missing_outside_holdout_group_in_concealed_identity",
                })
                continue
            prediction = classifier.classify(_crop_label(root, label), region=None)
            true_tile = label["tile_id"]
            predicted_tile = prediction.tile_id
            row = {
                "group": held_out,
                "image": label["image"],
                "region": _canonical_region(label["region"]),
                "true_tile": true_tile,
                "predicted_tile": predicted_tile,
                "confidence": prediction.confidence,
                "correct": predicted_tile == true_tile,
                "true_category": category_for(true_tile),
                "predicted_category": category_for(predicted_tile),
                "category_correct": (
                    category_for(predicted_tile) == category_for(true_tile)
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
    report.update({
        "schema_version": "vision_runtime_v0_2_concealed_identity_eval_v0_1",
        "method": "leave_source_session_out_hand_plus_draw_visual",
        "template_scope": "concealed_identity",
        "distinct_source_groups": len(groups),
        "unscorable": unscorable,
        "predictions": rows,
        "runtime_gate": _runtime_gate_summary(rows),
        "diagnostic_only": True,
        "changes_runtime_behavior": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    })
    return report


def evaluate_regional_identity(
    dataset_root: str | Path = "dataset/tiles_runtime_v0_2",
    *,
    confidence_threshold: float = 0.82,
) -> dict:
    """Evaluate the current hand-vs-draw regional classifier strategy."""
    root = Path(dataset_root)
    labels = [
        row for row in approved_labels(root)
        if _canonical_region(row["region"]) in {"hand_region", "draw_visual"}
    ]
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in labels:
        groups[_group_key(row)].append(row)

    rows = []
    unscorable = []
    all_labels = tuple(labels)
    for held_out, test_labels in sorted(groups.items()):
        for label in test_labels:
            region = _canonical_region(label["region"])
            train_labels = tuple(
                row for row in all_labels
                if _group_key(row) != held_out
                and _canonical_region(row["region"]) == region
            )
            train_classes = {row["tile_id"] for row in train_labels}
            if label["tile_id"] not in train_classes:
                unscorable.append({
                    "group": held_out,
                    "image": label["image"],
                    "tile_id": label["tile_id"],
                    "region": region,
                    "reason": "true_class_missing_outside_holdout_group_in_region",
                })
                continue
            classifier = TemplateTileClassifier.from_labels(root, train_labels)
            prediction = classifier.classify(
                _crop_label(root, label),
                region=region,
            )
            true_tile = label["tile_id"]
            predicted_tile = prediction.tile_id
            row = {
                "group": held_out,
                "image": label["image"],
                "region": region,
                "true_tile": true_tile,
                "predicted_tile": predicted_tile,
                "confidence": prediction.confidence,
                "correct": predicted_tile == true_tile,
                "true_category": category_for(true_tile),
                "predicted_category": category_for(predicted_tile),
                "category_correct": (
                    category_for(predicted_tile) == category_for(true_tile)
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
    report.update({
        "schema_version": "vision_runtime_v0_2_regional_identity_eval_v0_1",
        "method": "leave_source_session_out_current_regional_strategy",
        "template_scope": "same_runtime_region",
        "distinct_source_groups": len(groups),
        "unscorable": unscorable,
        "predictions": rows,
        "runtime_gate": _runtime_gate_summary(rows),
        "diagnostic_only": True,
        "changes_runtime_behavior": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    })
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate pooled hand/draw Runtime identity templates"
    )
    parser.add_argument("--dataset", default="dataset/tiles_runtime_v0_2")
    parser.add_argument("--confidence", type=float, default=0.82)
    parser.add_argument("--output")
    args = parser.parse_args()
    report = evaluate_concealed_identity(
        args.dataset,
        confidence_threshold=args.confidence,
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
