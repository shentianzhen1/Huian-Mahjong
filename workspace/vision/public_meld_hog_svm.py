"""Development-only linear-SVM check for exposed-meld identity.

This is the final cheap learned-boundary experiment before considering a compact
CNN. It reuses the fixed manual-HOG embedding and the same synthetic
hand-to-player-meld rendering. One-vs-rest linear SVMs are trained with a fixed
configuration; no parameter search is performed on the reviewed meld queries.

Per-class raw margins are oriented and linearly calibrated from their training
positive/negative means so the existing Mahjong-valid three-face group decoder
can consume comparable class scores.

Development evidence only: Runtime/Hint/Executor remain unchanged.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from PIL import Image

from workspace.vision.public_meld_face_segmentation import prepare_public_meld_faces
from workspace.vision.public_meld_group_identity_decoder import (
    rank_regular_public_meld_identity,
)
from workspace.vision.public_meld_hog_embedding import _hog_embedding
from workspace.vision.public_meld_synthetic_transfer import (
    _balanced_hand_labels,
    _pixel_bbox,
    _regular_player_meld_samples,
    render_self_meld_variants,
)
from workspace.vision.public_tile_detector import PublicGeometryCandidate


SVM_C = 1.0
SVM_MAX_ITERATIONS = 500
NEGATIVE_TO_POSITIVE_RATIO = 3


@dataclass
class OneVsRestModel:
    tile_id: str
    model: Any
    orientation: float
    negative_mean: float
    positive_mean: float


def _training_rows(dataset_root: Path) -> tuple[Any, list[str]]:
    import numpy as np

    vectors: list[Any] = []
    labels: list[str] = []
    for row in _balanced_hand_labels(dataset_root):
        tile_id = row.get("tile_id")
        image_value = row.get("image")
        if not isinstance(tile_id, str) or not isinstance(image_value, str):
            continue
        image_path = (dataset_root / image_value).resolve()
        if dataset_root.resolve() not in image_path.parents:
            raise ValueError("hand template path escapes dataset root")
        with Image.open(image_path) as source:
            image = source.convert("RGB")
        for variant in render_self_meld_variants(image):
            vector = _hog_embedding(variant)
            if vector is None:
                continue
            vectors.append(vector)
            labels.append(tile_id)
    if not vectors:
        raise ValueError("SVM synthetic training set is empty")
    return np.stack(vectors).astype("float32", copy=False), labels


def _balanced_binary_indices(
    labels: list[str],
    positive_tile: str,
) -> tuple[list[int], list[int]]:
    positives = [index for index, tile in enumerate(labels) if tile == positive_tile]
    if not positives:
        return [], []

    by_negative_class: dict[str, list[int]] = defaultdict(list)
    for index, tile in enumerate(labels):
        if tile != positive_tile:
            by_negative_class[tile].append(index)

    target = min(
        sum(len(rows) for rows in by_negative_class.values()),
        len(positives) * NEGATIVE_TO_POSITIVE_RATIO,
    )
    negatives: list[int] = []
    class_names = sorted(by_negative_class)
    offset = 0
    while len(negatives) < target:
        added = False
        for tile in class_names:
            rows = by_negative_class[tile]
            if offset < len(rows):
                negatives.append(rows[offset])
                added = True
                if len(negatives) >= target:
                    break
        if not added:
            break
        offset += 1
    return positives, negatives


def _fit_ovr_models(features: Any, labels: list[str]) -> dict[str, OneVsRestModel]:
    import cv2
    import numpy as np

    if not hasattr(cv2, "ml") or not hasattr(cv2.ml, "SVM_create"):
        raise RuntimeError("OpenCV ml.SVM is unavailable")

    models: dict[str, OneVsRestModel] = {}
    for tile_id in sorted(set(labels)):
        positives, negatives = _balanced_binary_indices(labels, tile_id)
        if not positives or not negatives:
            continue
        indices = positives + negatives
        x = features[indices].astype("float32", copy=False)
        y = np.asarray(
            [1] * len(positives) + [-1] * len(negatives),
            dtype=np.int32,
        ).reshape(-1, 1)

        svm = cv2.ml.SVM_create()
        svm.setType(cv2.ml.SVM_C_SVC)
        svm.setKernel(cv2.ml.SVM_LINEAR)
        svm.setC(SVM_C)
        svm.setTermCriteria(
            (cv2.TERM_CRITERIA_MAX_ITER, SVM_MAX_ITERATIONS, 1e-6)
        )
        if not svm.train(x, cv2.ml.ROW_SAMPLE, y):
            continue

        _, raw = svm.predict(x, flags=cv2.ml.STAT_MODEL_RAW_OUTPUT)
        raw_values = raw.reshape(-1).astype("float64", copy=False)
        positive_raw = raw_values[: len(positives)]
        negative_raw = raw_values[len(positives) :]
        raw_pos_mean = float(np.mean(positive_raw))
        raw_neg_mean = float(np.mean(negative_raw))
        orientation = 1.0 if raw_pos_mean > raw_neg_mean else -1.0
        positive_mean = orientation * raw_pos_mean
        negative_mean = orientation * raw_neg_mean
        if positive_mean - negative_mean <= 1e-9:
            continue
        models[tile_id] = OneVsRestModel(
            tile_id=tile_id,
            model=svm,
            orientation=orientation,
            negative_mean=negative_mean,
            positive_mean=positive_mean,
        )
    return models


def _svm_scores(query: Any, models: dict[str, OneVsRestModel]) -> dict[str, float]:
    import cv2
    import numpy as np

    if query is None:
        return {}
    row = np.asarray(query, dtype=np.float32).reshape(1, -1)
    scores: dict[str, float] = {}
    for tile_id, record in models.items():
        _, raw = record.model.predict(row, flags=cv2.ml.STAT_MODEL_RAW_OUTPUT)
        margin = record.orientation * float(raw.reshape(-1)[0])
        scale = record.positive_mean - record.negative_mean
        scores[tile_id] = (margin - record.negative_mean) / scale
    return scores


def _top1(scores: dict[str, float]) -> tuple[str | None, float | None]:
    if not scores:
        return None, None
    tile_id, score = min(scores.items(), key=lambda row: (-row[1], row[0]))
    return tile_id, float(score)


def evaluate_public_meld_hog_svm(
    repository_root: str | Path = ".",
    dataset_root: str | Path = "dataset/tiles_runtime_v0_2",
    calibration_path: str | Path = (
        "references/vision/2026-09-22/public_detector_calibration_v0_1.json"
    ),
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    dataset = (root / dataset_root).resolve()
    calibration = json.loads((root / calibration_path).read_text(encoding="utf-8"))
    samples = _regular_player_meld_samples(calibration)
    train_x, train_labels = _training_rows(dataset)
    models = _fit_ovr_models(train_x, train_labels)
    if not models:
        raise ValueError("no HOG SVM models trained")

    face_rows: list[dict[str, Any]] = []
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
            normalized_bbox=tuple(float(value) for value in sample["bbox"]),
            geometry_kind="bottom_group",
            confidence=1.0,
            fill_ratio=1.0,
            frame=sample.get("frame_index"),
            session=sample.get("source_session"),
        )
        prepared = prepare_public_meld_faces(image, group)
        if len(prepared.face_images) != 3:
            group_rows.append(
                {
                    "sample_id": sample["sample_id"],
                    "expected_tiles": list(sample["expected_tiles"]),
                    "prepared_face_count": len(prepared.face_images),
                    "group_correct": False,
                    "reason": "not_three_classifier_ready_faces",
                }
            )
            continue

        face_scores: list[dict[str, float]] = []
        for face_index, (face, expected_tile) in enumerate(
            zip(prepared.face_images, sample["expected_tiles"])
        ):
            query = _hog_embedding(face)
            scores = _svm_scores(query, models)
            predicted, score = _top1(scores)
            face_scores.append(scores)
            face_rows.append(
                {
                    "sample_id": sample["sample_id"],
                    "face_index": face_index,
                    "expected_tile": expected_tile,
                    "top1": predicted,
                    "top1_score": round(score, 8) if score is not None else None,
                    "top1_correct": predicted == expected_tile,
                }
            )

        ranking = rank_regular_public_meld_identity(face_scores)
        expected_sorted = sorted(sample["expected_tiles"])
        group_correct = (
            ranking.top_tiles is not None
            and sorted(ranking.top_tiles) == expected_sorted
        )
        group_rows.append(
            {
                "sample_id": sample["sample_id"],
                "expected_tiles": list(sample["expected_tiles"]),
                "prepared_face_count": 3,
                "group_tiles": (
                    list(ranking.top_tiles) if ranking.top_tiles is not None else None
                ),
                "group_correct": group_correct,
                "group_margin": ranking.margin,
            }
        )

    scorable_groups = [
        row for row in group_rows if row.get("prepared_face_count") == 3
    ]
    face_count = len(face_rows)
    group_count = len(scorable_groups)
    face_correct = sum(bool(row["top1_correct"]) for row in face_rows)
    group_correct = sum(bool(row["group_correct"]) for row in scorable_groups)

    return {
        "schema_version": "public_meld_hog_svm_v0_1",
        "method": "synthetic_meld_manual_hog_one_vs_rest_linear_svm",
        "fixed_profile": {
            "svm_c": SVM_C,
            "maximum_iterations": SVM_MAX_ITERATIONS,
            "negative_to_positive_ratio": NEGATIVE_TO_POSITIVE_RATIO,
            "margin_calibration": "oriented_train_negative_mean_to_positive_mean",
            "parameter_search": False,
        },
        "training_sample_count": int(train_x.shape[0]),
        "training_class_count": len(set(train_labels)),
        "trained_model_count": len(models),
        "target_group_count": len(samples),
        "scored_group_count": group_count,
        "scored_face_count": face_count,
        "face_top1_correct": face_correct,
        "face_top1_accuracy": round(face_correct / face_count, 6) if face_count else None,
        "group_top1_correct": group_correct,
        "group_top1_accuracy": (
            round(group_correct / group_count, 6) if group_count else None
        ),
        "faces": face_rows,
        "groups": group_rows,
        "evidence_role": "development_selection_only",
        "blind_validation": False,
        "opponent_top_group_accuracy_measured": False,
        "changes_runtime_behavior": False,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
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
    parser.add_argument("--output")
    args = parser.parse_args()
    report = evaluate_public_meld_hog_svm(
        args.repository_root,
        args.dataset,
        args.calibration,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
