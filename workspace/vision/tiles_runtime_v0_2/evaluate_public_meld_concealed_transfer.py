"""Diagnostic A/B: normalized public meld faces vs concealed identity bank.

This report asks one narrow engineering question: after the new exposed-meld
geometry normalization and 3-face split, does the already mature
hand/draw (concealed_identity) template bank transfer well enough to justify
further work?

It never changes Runtime behavior. Public identity remains UNKNOWN unless the
separate public-region gate says otherwise. Source-session exclusion here uses
only exact runtime/public session strings and is therefore diagnostic, not
formal source-disjoint promotion evidence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image

from workspace.vision.public_meld_face_segmentation import prepare_public_meld_faces
from workspace.vision.public_tile_detector import PublicGeometryCandidate
from workspace.vision.tiles_v0_1.labels import approved_labels
from workspace.vision.tiles_v0_1.template_classifier import TemplateTileClassifier

from .runtime_reader import (
    CONCEALED_IDENTITY_GATE_REGION,
    CONCEALED_IDENTITY_SOURCE_REGIONS,
    _canonical_region,
    _coverage,
    _training_labels,
    identity_gate,
)


def _pixel_bbox(
    normalized_bbox: list[float] | tuple[float, float, float, float],
    size: tuple[int, int],
) -> tuple[int, int, int, int]:
    frame_width, frame_height = size
    x, y, width, height = (float(value) for value in normalized_bbox)
    left = max(0, int(round(x * frame_width)))
    top = max(0, int(round(y * frame_height)))
    right = min(frame_width, int(round((x + width) * frame_width)))
    bottom = min(frame_height, int(round((y + height) * frame_height)))
    return left, top, max(0, right - left), max(0, bottom - top)


def _public_meld_samples(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in payload.get("samples", ())
        if (
            row.get("target") == "meld"
            and isinstance(row.get("expected_tiles"), list)
            and len(row["expected_tiles"]) == 3
            and row.get("status") == "bbox_reviewed"
        )
    ]


def evaluate_public_meld_concealed_transfer(
    repository_root: str | Path = ".",
    dataset_root: str | Path = "dataset/tiles_runtime_v0_2",
    calibration_path: str | Path = (
        "references/vision/2026-09-22/public_detector_calibration_v0_1.json"
    ),
    *,
    confidence_threshold: float = 0.82,
) -> dict[str, Any]:
    if (
        isinstance(confidence_threshold, bool)
        or not isinstance(confidence_threshold, (int, float))
        or not 0 <= float(confidence_threshold) <= 1
    ):
        raise ValueError("confidence_threshold must be between 0 and 1")

    root = Path(repository_root).resolve()
    dataset = (root / dataset_root).resolve()
    calibration = json.loads((root / calibration_path).read_text(encoding="utf-8"))
    samples = _public_meld_samples(calibration)

    runtime_labels = [
        row
        for row in approved_labels(dataset)
        if (
            _canonical_region(row["region"]) in CONCEALED_IDENTITY_SOURCE_REGIONS
            and not row.get("gold_skin_only")
        )
    ]
    if not runtime_labels:
        raise ValueError("concealed identity dataset is empty")

    rows: list[dict[str, Any]] = []
    group_rows: list[dict[str, Any]] = []
    for sample in samples:
        image_path = (root / sample["image_path"]).resolve()
        if root not in image_path.parents:
            raise ValueError("public meld image escapes repository root")
        with Image.open(image_path) as source:
            image = source.convert("RGB")

        bbox = _pixel_bbox(sample["bbox"], image.size)
        group = PublicGeometryCandidate(
            pixel_bbox=bbox,
            normalized_bbox=tuple(float(v) for v in sample["bbox"]),
            geometry_kind="bottom_group",
            confidence=1.0,
            fill_ratio=1.0,
            frame=sample.get("frame_index"),
            session=sample.get("source_session"),
        )
        prepared = prepare_public_meld_faces(image, group)
        prepared_count = len(prepared.face_images)
        group_rows.append({
            "sample_id": sample["sample_id"],
            "source_session": sample["source_session"],
            "expected_tiles": list(sample["expected_tiles"]),
            "stack_state": prepared.geometry.stack_state,
            "prepared_face_count": prepared_count,
            "geometry_issues": list(prepared.geometry.issues),
        })
        if prepared_count != 3:
            continue

        train_labels = _training_labels(
            runtime_labels,
            sample.get("source_session"),
        )
        excluded_training_labels = len(runtime_labels) - len(train_labels)
        classifier = TemplateTileClassifier.from_labels(dataset, train_labels)
        _, covered_by_region, cross_session = _coverage(train_labels)
        covered = covered_by_region.get(CONCEALED_IDENTITY_GATE_REGION, set())

        for index, (face, expected) in enumerate(
            zip(prepared.face_images, sample["expected_tiles"])
        ):
            prediction = classifier.classify(
                face,
                region=CONCEALED_IDENTITY_GATE_REGION,
            )
            gated_tile, gate_reason = identity_gate(
                prediction.tile_id,
                prediction.confidence,
                region=CONCEALED_IDENTITY_GATE_REGION,
                covered_classes=covered,
                cross_session_classes=cross_session,
                confidence_threshold=float(confidence_threshold),
            )
            rows.append({
                "sample_id": sample["sample_id"],
                "source_session": sample["source_session"],
                "face_index": index,
                "expected_tile": expected,
                "predicted_tile": prediction.tile_id,
                "confidence": round(float(prediction.confidence), 6),
                "raw_correct": prediction.tile_id == expected,
                "runtime_gate_tile": gated_tile,
                "runtime_gate_reason": gate_reason,
                "runtime_gate_accepted": gated_tile != "UNKNOWN",
                "runtime_gate_correct": gated_tile == expected,
                "excluded_training_labels_by_exact_session": excluded_training_labels,
            })

    accepted = [row for row in rows if row["runtime_gate_accepted"]]
    correct = sum(bool(row["raw_correct"]) for row in rows)
    accepted_correct = sum(bool(row["runtime_gate_correct"]) for row in accepted)
    exact_exclusion_effective = any(
        row["excluded_training_labels_by_exact_session"] > 0 for row in rows
    )

    return {
        "schema_version": "public_meld_concealed_transfer_eval_v0_1",
        "method": "normalize_group_then_split_then_concealed_identity_templates",
        "confidence_threshold": float(confidence_threshold),
        "target_group_count": len(samples),
        "target_face_count": sum(len(row["expected_tiles"]) for row in samples),
        "prepared_group_count": sum(
            row["prepared_face_count"] == 3 for row in group_rows
        ),
        "scored_face_count": len(rows),
        "raw_exact_accuracy": (
            round(correct / len(rows), 6) if rows else None
        ),
        "runtime_gate_accepted_count": len(accepted),
        "runtime_gate_accepted_accuracy": (
            round(accepted_correct / len(accepted), 6) if accepted else None
        ),
        "exact_session_exclusion_effective": exact_exclusion_effective,
        "groups": group_rows,
        "predictions": rows,
        "diagnostic_only": True,
        "changes_runtime_behavior": False,
        "formal_promotion_evidence": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--dataset", default="dataset/tiles_runtime_v0_2")
    parser.add_argument(
        "--calibration",
        default="references/vision/2026-09-22/public_detector_calibration_v0_1.json",
    )
    parser.add_argument("--confidence", type=float, default=0.82)
    args = parser.parse_args()
    report = evaluate_public_meld_concealed_transfer(
        args.repository_root,
        args.dataset,
        args.calibration,
        confidence_threshold=args.confidence,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
