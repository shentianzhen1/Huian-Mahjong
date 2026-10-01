"""Development-only LinearSVC check for exposed-meld identity.

This is the final cheap learned-boundary experiment before considering a compact
CNN. It reuses the fixed manual-HOG embedding and the same synthetic
hand-to-player-meld rendering. A fixed scikit-learn LinearSVC is trained only
on synthetic transforms of reviewed concealed-hand crops; reviewed public-meld
queries are evaluation-only.

scikit-learn is an experiment-only CI dependency and is not added to Runtime,
Hint Alpha, or the package's normal Vision dependency set.
"""
from __future__ import annotations

import argparse
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
SVM_MAX_ITERATIONS = 5000
SVM_CLASS_WEIGHT = "balanced"
SVM_DUAL = "auto"
SVM_RANDOM_STATE = 0


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


def _fit_classifier(features: Any, labels: list[str]) -> Any:
    from sklearn.svm import LinearSVC

    classifier = LinearSVC(
        C=SVM_C,
        class_weight=SVM_CLASS_WEIGHT,
        dual=SVM_DUAL,
        max_iter=SVM_MAX_ITERATIONS,
        random_state=SVM_RANDOM_STATE,
    )
    classifier.fit(features, labels)
    return classifier


def _svm_scores(query: Any, classifier: Any) -> dict[str, float]:
    import numpy as np

    if query is None:
        return {}
    row = np.asarray(query, dtype=np.float32).reshape(1, -1)
    raw = classifier.decision_function(row)
    classes = [str(tile_id) for tile_id in classifier.classes_]
    values = np.asarray(raw, dtype=np.float64)
    if len(classes) == 2:
        margin = float(values.reshape(-1)[0])
        return {
            classes[0]: -margin,
            classes[1]: margin,
        }
    if values.ndim == 1:
        values = values.reshape(1, -1)
    return {
        tile_id: float(score)
        for tile_id, score in zip(classes, values[0])
        if np.isfinite(score)
    }


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
    classifier = _fit_classifier(train_x, train_labels)

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
            scores = _svm_scores(query, classifier)
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
        "schema_version": "public_meld_hog_svm_v0_2",
        "method": "synthetic_meld_manual_hog_sklearn_linear_svc",
        "fixed_profile": {
            "svm_c": SVM_C,
            "class_weight": SVM_CLASS_WEIGHT,
            "dual": SVM_DUAL,
            "maximum_iterations": SVM_MAX_ITERATIONS,
            "random_state": SVM_RANDOM_STATE,
            "parameter_search": False,
        },
        "training_sample_count": int(train_x.shape[0]),
        "training_class_count": len(set(train_labels)),
        "trained_class_count": len(classifier.classes_),
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
        "experiment_only_dependency": "scikit-learn",
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
