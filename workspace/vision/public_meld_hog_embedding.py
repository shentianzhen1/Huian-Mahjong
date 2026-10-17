"""Development-only HOG embedding A/B for exposed-meld identity.

This is a deliberately small, dependency-light representation test before any
CNN is introduced. Reviewed concealed-hand crops are rendered into the same
synthetic player-meld domain used by the prior SIFT transfer experiment. A
global HOG descriptor is then averaged into one prototype per tile class.

Why this exists:
- SIFT is local-keypoint based and has struggled on tiny exposed tiles.
- HOG retains the whole normalized glyph/shape field.
- cosine-to-class-prototype yields comparable per-class scores that can be
  passed directly to the existing Mahjong-valid three-face group decoder.

This is development/selection evidence only. It does not change Runtime, Hint,
Executor, identity thresholds, or formal promotion state.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from typing import Any

from PIL import Image

from workspace.vision.public_meld_face_segmentation import prepare_public_meld_faces
from workspace.vision.public_meld_group_identity_decoder import (
    rank_regular_public_meld_identity,
)
from workspace.vision.public_meld_synthetic_transfer import (
    _balanced_hand_labels,
    _canonical_face,
    _pixel_bbox,
    _regular_player_meld_samples,
    render_self_meld_variants,
)
from workspace.vision.public_tile_detector import PublicGeometryCandidate


HOG_WIN_SIZE = (56, 96)
HOG_BLOCK_SIZE = (16, 16)
HOG_BLOCK_STRIDE = (8, 8)
HOG_CELL_SIZE = (8, 8)
HOG_BINS = 9
HOG_CLAHE_CLIP_LIMIT = 2.0
HOG_CLAHE_GRID = (8, 8)


def _hog_embedding(image: Any) -> Any:
    import cv2
    import numpy as np

    canonical = _canonical_face(image).convert("RGB")
    rgb = np.asarray(canonical, dtype=np.uint8)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(
        clipLimit=HOG_CLAHE_CLIP_LIMIT,
        tileGridSize=HOG_CLAHE_GRID,
    )
    normalized = clahe.apply(gray)
    field = normalized.astype("float32", copy=False)
    gradient_y, gradient_x = np.gradient(field)
    magnitude = np.hypot(gradient_x, gradient_y)
    angle = (np.degrees(np.arctan2(gradient_y, gradient_x)) % 180.0)

    cell_w, cell_h = HOG_CELL_SIZE
    width, height = HOG_WIN_SIZE
    cells_x = width // cell_w
    cells_y = height // cell_h
    hist = np.zeros((cells_y, cells_x, HOG_BINS), dtype=np.float32)
    bin_width = 180.0 / HOG_BINS

    for cell_y in range(cells_y):
        y0 = cell_y * cell_h
        y1 = y0 + cell_h
        for cell_x in range(cells_x):
            x0 = cell_x * cell_w
            x1 = x0 + cell_w
            cell_angles = angle[y0:y1, x0:x1].reshape(-1)
            cell_magnitude = magnitude[y0:y1, x0:x1].reshape(-1)
            bins = np.floor(cell_angles / bin_width).astype(np.int32) % HOG_BINS
            hist[cell_y, cell_x] = np.bincount(
                bins,
                weights=cell_magnitude,
                minlength=HOG_BINS,
            )[:HOG_BINS]

    block_cells_x = HOG_BLOCK_SIZE[0] // cell_w
    block_cells_y = HOG_BLOCK_SIZE[1] // cell_h
    stride_cells_x = HOG_BLOCK_STRIDE[0] // cell_w
    stride_cells_y = HOG_BLOCK_STRIDE[1] // cell_h
    blocks: list[Any] = []
    for cell_y in range(0, cells_y - block_cells_y + 1, stride_cells_y):
        for cell_x in range(0, cells_x - block_cells_x + 1, stride_cells_x):
            block = hist[
                cell_y : cell_y + block_cells_y,
                cell_x : cell_x + block_cells_x,
            ].reshape(-1)
            norm = float(np.sqrt(np.dot(block, block) + 1e-6))
            block = block / norm
            block = np.minimum(block, 0.2)
            norm = float(np.sqrt(np.dot(block, block) + 1e-6))
            blocks.append((block / norm).astype("float32", copy=False))

    if not blocks:
        return None
    vector = np.concatenate(blocks).astype("float32", copy=False)
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-12:
        return None
    return vector / norm


def _class_prototypes(
    repository_root: Path,
    dataset_root: Path,
    *,
    synthetic: bool,
) -> dict[str, Any]:
    import numpy as np

    grouped: dict[str, list[Any]] = defaultdict(list)
    for row in _balanced_hand_labels(dataset_root):
        tile_id = row.get("tile_id")
        image_path_value = row.get("image")
        if not isinstance(tile_id, str) or not isinstance(image_path_value, str):
            continue
        image_path = (dataset_root / image_path_value).resolve()
        if dataset_root.resolve() not in image_path.parents:
            raise ValueError("hand template path escapes dataset root")
        with Image.open(image_path) as source:
            image = source.convert("RGB")
        variants = render_self_meld_variants(image) if synthetic else (image,)
        for variant in variants:
            embedding = _hog_embedding(variant)
            if embedding is not None:
                grouped[tile_id].append(embedding)

    prototypes: dict[str, Any] = {}
    for tile_id, vectors in grouped.items():
        if not vectors:
            continue
        mean = np.mean(np.stack(vectors, axis=0), axis=0).astype(
            "float32", copy=False
        )
        norm = float(np.linalg.norm(mean))
        if norm <= 1e-12:
            continue
        prototypes[tile_id] = mean / norm
    return prototypes


def _prototype_scores(query: Any, prototypes: dict[str, Any]) -> dict[str, float]:
    import numpy as np

    if query is None:
        return {}
    scores: dict[str, float] = {}
    for tile_id, prototype in prototypes.items():
        score = float(np.dot(query, prototype))
        if np.isfinite(score):
            scores[tile_id] = score
    return scores


def _top1(scores: dict[str, float]) -> tuple[str | None, float | None]:
    if not scores:
        return None, None
    tile_id, score = min(scores.items(), key=lambda row: (-row[1], row[0]))
    return tile_id, float(score)


def evaluate_public_meld_hog_embedding(
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

    raw_prototypes = _class_prototypes(root, dataset, synthetic=False)
    synthetic_prototypes = _class_prototypes(root, dataset, synthetic=True)
    if not raw_prototypes or not synthetic_prototypes:
        raise ValueError("HOG prototype bank is empty")

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
                    "raw_group_correct": False,
                    "synthetic_group_correct": False,
                    "reason": "not_three_classifier_ready_faces",
                }
            )
            continue

        raw_face_scores: list[dict[str, float]] = []
        synthetic_face_scores: list[dict[str, float]] = []
        for face_index, (face, expected_tile) in enumerate(
            zip(prepared.face_images, sample["expected_tiles"])
        ):
            query = _hog_embedding(face)
            raw_scores = _prototype_scores(query, raw_prototypes)
            synthetic_scores = _prototype_scores(query, synthetic_prototypes)
            raw_tile, raw_score = _top1(raw_scores)
            synthetic_tile, synthetic_score = _top1(synthetic_scores)
            raw_face_scores.append(raw_scores)
            synthetic_face_scores.append(synthetic_scores)
            face_rows.append(
                {
                    "sample_id": sample["sample_id"],
                    "face_index": face_index,
                    "expected_tile": expected_tile,
                    "raw_top1": raw_tile,
                    "raw_score": round(raw_score, 8) if raw_score is not None else None,
                    "raw_correct": raw_tile == expected_tile,
                    "synthetic_top1": synthetic_tile,
                    "synthetic_score": (
                        round(synthetic_score, 8)
                        if synthetic_score is not None
                        else None
                    ),
                    "synthetic_correct": synthetic_tile == expected_tile,
                }
            )

        raw_group = rank_regular_public_meld_identity(raw_face_scores)
        synthetic_group = rank_regular_public_meld_identity(synthetic_face_scores)
        expected_sorted = sorted(sample["expected_tiles"])
        raw_group_correct = (
            raw_group.top_tiles is not None
            and sorted(raw_group.top_tiles) == expected_sorted
        )
        synthetic_group_correct = (
            synthetic_group.top_tiles is not None
            and sorted(synthetic_group.top_tiles) == expected_sorted
        )
        group_rows.append(
            {
                "sample_id": sample["sample_id"],
                "expected_tiles": list(sample["expected_tiles"]),
                "prepared_face_count": 3,
                "raw_group_tiles": (
                    list(raw_group.top_tiles) if raw_group.top_tiles is not None else None
                ),
                "raw_group_correct": raw_group_correct,
                "synthetic_group_tiles": (
                    list(synthetic_group.top_tiles)
                    if synthetic_group.top_tiles is not None
                    else None
                ),
                "synthetic_group_correct": synthetic_group_correct,
            }
        )

    scorable_groups = [
        row for row in group_rows if row.get("prepared_face_count") == 3
    ]
    face_count = len(face_rows)
    group_count = len(scorable_groups)
    raw_face_correct = sum(bool(row["raw_correct"]) for row in face_rows)
    synthetic_face_correct = sum(
        bool(row["synthetic_correct"]) for row in face_rows
    )
    raw_group_correct = sum(
        bool(row["raw_group_correct"]) for row in scorable_groups
    )
    synthetic_group_correct = sum(
        bool(row["synthetic_group_correct"]) for row in scorable_groups
    )

    def ratio(correct: int, total: int) -> float | None:
        return round(correct / total, 6) if total else None

    return {
        "schema_version": "public_meld_hog_embedding_v0_1",
        "method": "global_hog_cosine_class_prototype_plus_legal_group_decoder",
        "profile": {
            "win_size": list(HOG_WIN_SIZE),
            "block_size": list(HOG_BLOCK_SIZE),
            "block_stride": list(HOG_BLOCK_STRIDE),
            "cell_size": list(HOG_CELL_SIZE),
            "bins": HOG_BINS,
            "clahe_clip_limit": HOG_CLAHE_CLIP_LIMIT,
            "clahe_grid": list(HOG_CLAHE_GRID),
            "prototype_aggregation": "l2_normalized_mean_then_l2_normalize",
            "score": "cosine_dot_product",
        },
        "raw_hand_prototype_class_count": len(raw_prototypes),
        "synthetic_meld_prototype_class_count": len(synthetic_prototypes),
        "target_group_count": len(samples),
        "scored_group_count": group_count,
        "scored_face_count": face_count,
        "raw_hand_hog": {
            "face_top1_correct": raw_face_correct,
            "face_top1_accuracy": ratio(raw_face_correct, face_count),
            "group_top1_correct": raw_group_correct,
            "group_top1_accuracy": ratio(raw_group_correct, group_count),
        },
        "synthetic_meld_hog": {
            "face_top1_correct": synthetic_face_correct,
            "face_top1_accuracy": ratio(synthetic_face_correct, face_count),
            "group_top1_correct": synthetic_group_correct,
            "group_top1_accuracy": ratio(synthetic_group_correct, group_count),
        },
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
    report = evaluate_public_meld_hog_embedding(
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
