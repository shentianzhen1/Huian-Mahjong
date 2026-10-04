"""Development-only MobileNetV3 embedding experiment for public meld identity.

This is the first compact learned-image-representation test after closing the
manual SIFT/HOG branch. It deliberately freezes an ImageNet-pretrained
MobileNetV3-Small backbone and evaluates source-group-separated real public-meld
queries without fine-tuning on the reviewed query set.

Two prototype policies are compared for every held-out original match group:
1. synthetic_only: class prototypes come from concealed-hand crops rendered
   into the player exposed-meld domain;
2. real_first: if a class has reviewed real exposed-meld faces from OTHER
   original match groups, their mean embedding is used; otherwise the synthetic
   prototype is the fallback.

The held-out original match group never contributes real meld pixels to its own
prototype bank. One known concealed-template session from the older eight-hand
match is also excluded when that match group is held out.

This remains development/selection evidence. The concealed-template lineage is
not complete enough to call this a formal blind holdout, and opponent top_group
identity still has no reviewed ground-truth batch.

torch/torchvision are experiment-only CI dependencies; Runtime/Hint/Executor and
normal project dependencies remain unchanged.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from PIL import Image

from workspace.vision.public_identity_shadow_v0_2 import load_development_sources
from workspace.vision.public_meld_face_segmentation import prepare_public_meld_faces
from workspace.vision.public_meld_group_identity_decoder import (
    rank_regular_public_meld_identity,
)
from workspace.vision.public_meld_synthetic_transfer import (
    _balanced_hand_labels,
    _pixel_bbox,
    _regular_player_meld_samples,
    render_self_meld_variants,
)
from workspace.vision.public_tile_detector import PublicGeometryCandidate


MODEL_NAME = "mobilenet_v3_small_imagenet1k_v1"
EMBEDDING_INPUT_SIZE = 224
BATCH_SIZE = 32
# Explicitly known same-match concealed-template source. Other concealed source
# sessions currently lack an original-match registry, which is why this
# experiment cannot be formal blind validation.
KNOWN_HAND_SESSION_MATCH_GROUPS = {
    "session_eight_hand_match_a": "reviewed_match_2026_09_19_eight_hand",
}


@dataclass(frozen=True)
class RealFace:
    sample_id: str
    tile_id: str
    source_session: str
    match_group: str
    image: Any


@dataclass(frozen=True)
class SyntheticFace:
    tile_id: str
    source_session: str | None
    image: Any


def _square_tile_canvas(image: Any) -> Any:
    """Place a normalized tile on a white square without changing aspect ratio."""
    tile = image.convert("RGB")
    target_height = 192
    scale = target_height / max(1, tile.height)
    target_width = max(1, int(round(tile.width * scale)))
    if target_width > 160:
        scale = 160 / max(1, tile.width)
        target_width = 160
        target_height = max(1, int(round(tile.height * scale)))
    resized = tile.resize((target_width, target_height), Image.Resampling.BICUBIC)
    canvas = Image.new("RGB", (EMBEDDING_INPUT_SIZE, EMBEDDING_INPUT_SIZE), "white")
    left = (EMBEDDING_INPUT_SIZE - target_width) // 2
    top = (EMBEDDING_INPUT_SIZE - target_height) // 2
    canvas.paste(resized, (left, top))
    return canvas


def _load_real_faces(
    root: Path,
    calibration: dict[str, Any],
    source_registry: Path,
) -> tuple[list[RealFace], list[dict[str, Any]]]:
    sources = load_development_sources(source_registry)
    faces: list[RealFace] = []
    groups: list[dict[str, Any]] = []

    for sample in _regular_player_meld_samples(calibration):
        source = sources.get(sample["source_session"])
        if source is None or source.source_sha256 != sample["source_sha256"]:
            raise ValueError("reviewed meld source is absent from source registry")
        image_path = (root / sample["image_path"]).resolve()
        if root not in image_path.parents:
            raise ValueError("public meld image escapes repository root")
        with Image.open(image_path) as original:
            image = original.convert("RGB")
        bbox = _pixel_bbox(sample["bbox"], image.size)
        candidate = PublicGeometryCandidate(
            pixel_bbox=bbox,
            normalized_bbox=tuple(float(value) for value in sample["bbox"]),
            geometry_kind="bottom_group",
            confidence=1.0,
            fill_ratio=1.0,
            frame=sample.get("frame_index"),
            session=sample.get("source_session"),
        )
        prepared = prepare_public_meld_faces(image, candidate)
        expected = list(sample["expected_tiles"])
        if len(prepared.face_images) != 3 or len(expected) != 3:
            continue
        start = len(faces)
        for tile_id, face in zip(expected, prepared.face_images):
            faces.append(
                RealFace(
                    sample_id=sample["sample_id"],
                    tile_id=tile_id,
                    source_session=sample["source_session"],
                    match_group=source.match_group,
                    image=_square_tile_canvas(face),
                )
            )
        groups.append(
            {
                "sample_id": sample["sample_id"],
                "expected_tiles": expected,
                "match_group": source.match_group,
                "face_indices": [start, start + 1, start + 2],
            }
        )
    return faces, groups


def _load_synthetic_faces(dataset_root: Path) -> list[SyntheticFace]:
    rows: list[SyntheticFace] = []
    for label in _balanced_hand_labels(dataset_root):
        tile_id = label.get("tile_id")
        image_value = label.get("image")
        if not isinstance(tile_id, str) or not isinstance(image_value, str):
            continue
        path = (dataset_root / image_value).resolve()
        if dataset_root.resolve() not in path.parents:
            raise ValueError("hand template path escapes dataset root")
        with Image.open(path) as original:
            image = original.convert("RGB")
        for variant in render_self_meld_variants(image):
            rows.append(
                SyntheticFace(
                    tile_id=tile_id,
                    source_session=label.get("source_session"),
                    image=_square_tile_canvas(variant),
                )
            )
    return rows


def _load_model() -> tuple[Any, Any, str]:
    import torch
    from torchvision.models import (
        MobileNet_V3_Small_Weights,
        mobilenet_v3_small,
    )
    from torchvision.transforms import Compose, Normalize, PILToTensor

    weights = MobileNet_V3_Small_Weights.IMAGENET1K_V1
    model = mobilenet_v3_small(weights=weights)
    model.classifier = torch.nn.Identity()
    model.eval()
    transform = Compose(
        [
            PILToTensor(),
            lambda tensor: tensor.float().div(255.0),
            Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ]
    )
    return model, transform, str(weights)


def _embed_images(images: list[Any], model: Any, transform: Any) -> Any:
    import numpy as np
    import torch

    vectors: list[Any] = []
    with torch.inference_mode():
        for start in range(0, len(images), BATCH_SIZE):
            batch_images = images[start : start + BATCH_SIZE]
            batch = torch.stack([transform(image) for image in batch_images], dim=0)
            output = model(batch).detach().cpu().numpy().astype("float32", copy=False)
            norms = np.linalg.norm(output, axis=1, keepdims=True)
            norms = np.maximum(norms, 1e-12)
            vectors.append(output / norms)
    if not vectors:
        return np.zeros((0, 0), dtype=np.float32)
    return np.concatenate(vectors, axis=0)


def _mean_prototypes(
    tile_ids: list[str],
    embeddings: Any,
    include: list[bool] | None = None,
) -> dict[str, Any]:
    import numpy as np

    grouped: dict[str, list[Any]] = defaultdict(list)
    for index, tile_id in enumerate(tile_ids):
        if include is not None and not include[index]:
            continue
        grouped[tile_id].append(embeddings[index])
    prototypes: dict[str, Any] = {}
    for tile_id, vectors in grouped.items():
        mean = np.mean(np.stack(vectors, axis=0), axis=0).astype(
            "float32", copy=False
        )
        norm = float(np.linalg.norm(mean))
        if norm > 1e-12:
            prototypes[tile_id] = mean / norm
    return prototypes


def _scores(query: Any, prototypes: dict[str, Any]) -> dict[str, float]:
    import numpy as np

    return {
        tile_id: float(np.dot(query, prototype))
        for tile_id, prototype in prototypes.items()
    }


def _top1(scores: dict[str, float]) -> str | None:
    if not scores:
        return None
    return min(scores.items(), key=lambda row: (-row[1], row[0]))[0]


def evaluate_public_meld_mobilenet_embedding(
    repository_root: str | Path = ".",
    dataset_root: str | Path = "dataset/tiles_runtime_v0_2",
    calibration_path: str | Path = (
        "references/vision/2026-09-22/public_detector_calibration_v0_1.json"
    ),
    source_registry_path: str | Path = (
        "references/vision/2026-09-24/public_identity_source_groups.development.json"
    ),
) -> dict[str, Any]:
    import numpy as np

    root = Path(repository_root).resolve()
    dataset = (root / dataset_root).resolve()
    calibration = json.loads((root / calibration_path).read_text(encoding="utf-8"))
    source_registry = (root / source_registry_path).resolve()

    real_faces, groups = _load_real_faces(root, calibration, source_registry)
    synthetic_faces = _load_synthetic_faces(dataset)
    if not real_faces or not synthetic_faces:
        raise ValueError("MobileNet experiment requires real and synthetic faces")

    model, transform, weight_name = _load_model()
    real_embeddings = _embed_images(
        [row.image for row in real_faces], model, transform
    )
    synthetic_embeddings = _embed_images(
        [row.image for row in synthetic_faces], model, transform
    )

    real_tile_ids = [row.tile_id for row in real_faces]
    synthetic_tile_ids = [row.tile_id for row in synthetic_faces]
    match_groups = sorted({row.match_group for row in real_faces})

    folds: list[dict[str, Any]] = []
    aggregate = {
        "synthetic_only_face_correct": 0,
        "real_first_face_correct": 0,
        "face_total": 0,
        "synthetic_only_group_correct": 0,
        "real_first_group_correct": 0,
        "group_total": 0,
    }

    for held_out in match_groups:
        synthetic_include = [
            KNOWN_HAND_SESSION_MATCH_GROUPS.get(row.source_session) != held_out
            for row in synthetic_faces
        ]
        synthetic_prototypes = _mean_prototypes(
            synthetic_tile_ids,
            synthetic_embeddings,
            synthetic_include,
        )
        real_include = [row.match_group != held_out for row in real_faces]
        real_prototypes = _mean_prototypes(
            real_tile_ids,
            real_embeddings,
            real_include,
        )
        real_first = dict(synthetic_prototypes)
        real_first.update(real_prototypes)

        fold_faces: list[dict[str, Any]] = []
        fold_groups: list[dict[str, Any]] = []
        query_indices = [
            index
            for index, row in enumerate(real_faces)
            if row.match_group == held_out
        ]
        for index in query_indices:
            expected = real_faces[index].tile_id
            synthetic_scores = _scores(
                real_embeddings[index], synthetic_prototypes
            )
            real_first_scores = _scores(real_embeddings[index], real_first)
            synthetic_top1 = _top1(synthetic_scores)
            real_first_top1 = _top1(real_first_scores)
            fold_faces.append(
                {
                    "face_index": index,
                    "sample_id": real_faces[index].sample_id,
                    "expected_tile": expected,
                    "synthetic_only_top1": synthetic_top1,
                    "synthetic_only_correct": synthetic_top1 == expected,
                    "real_first_top1": real_first_top1,
                    "real_first_correct": real_first_top1 == expected,
                    "real_template_available": expected in real_prototypes,
                }
            )

        for group in groups:
            if group["match_group"] != held_out:
                continue
            synthetic_rows = [
                _scores(real_embeddings[index], synthetic_prototypes)
                for index in group["face_indices"]
            ]
            real_first_rows = [
                _scores(real_embeddings[index], real_first)
                for index in group["face_indices"]
            ]
            synthetic_rank = rank_regular_public_meld_identity(synthetic_rows)
            real_first_rank = rank_regular_public_meld_identity(real_first_rows)
            expected_sorted = sorted(group["expected_tiles"])
            synthetic_correct = (
                synthetic_rank.top_tiles is not None
                and sorted(synthetic_rank.top_tiles) == expected_sorted
            )
            real_first_correct = (
                real_first_rank.top_tiles is not None
                and sorted(real_first_rank.top_tiles) == expected_sorted
            )
            fold_groups.append(
                {
                    "sample_id": group["sample_id"],
                    "expected_tiles": group["expected_tiles"],
                    "synthetic_only_tiles": (
                        list(synthetic_rank.top_tiles)
                        if synthetic_rank.top_tiles is not None
                        else None
                    ),
                    "synthetic_only_correct": synthetic_correct,
                    "real_first_tiles": (
                        list(real_first_rank.top_tiles)
                        if real_first_rank.top_tiles is not None
                        else None
                    ),
                    "real_first_correct": real_first_correct,
                }
            )

        fold_summary = {
            "held_out_match_group": held_out,
            "query_face_count": len(fold_faces),
            "query_group_count": len(fold_groups),
            "synthetic_only_face_correct": sum(
                bool(row["synthetic_only_correct"]) for row in fold_faces
            ),
            "real_first_face_correct": sum(
                bool(row["real_first_correct"]) for row in fold_faces
            ),
            "synthetic_only_group_correct": sum(
                bool(row["synthetic_only_correct"]) for row in fold_groups
            ),
            "real_first_group_correct": sum(
                bool(row["real_first_correct"]) for row in fold_groups
            ),
            "real_first_class_count": len(real_prototypes),
            "synthetic_class_count": len(synthetic_prototypes),
            "faces": fold_faces,
            "groups": fold_groups,
        }
        folds.append(fold_summary)
        aggregate["synthetic_only_face_correct"] += fold_summary[
            "synthetic_only_face_correct"
        ]
        aggregate["real_first_face_correct"] += fold_summary[
            "real_first_face_correct"
        ]
        aggregate["face_total"] += len(fold_faces)
        aggregate["synthetic_only_group_correct"] += fold_summary[
            "synthetic_only_group_correct"
        ]
        aggregate["real_first_group_correct"] += fold_summary[
            "real_first_group_correct"
        ]
        aggregate["group_total"] += len(fold_groups)

    face_total = aggregate["face_total"]
    group_total = aggregate["group_total"]

    def ratio(value: int, total: int) -> float | None:
        return round(value / total, 6) if total else None

    return {
        "schema_version": "public_meld_mobilenet_embedding_v0_1",
        "method": "frozen_mobilenet_v3_small_cosine_prototypes_leave_one_match_group_out",
        "model": {
            "name": MODEL_NAME,
            "weights": weight_name,
            "fine_tuned": False,
            "embedding_input_size": EMBEDDING_INPUT_SIZE,
        },
        "real_reviewed_face_count": len(real_faces),
        "real_reviewed_group_count": len(groups),
        "independent_match_group_count": len(match_groups),
        "synthetic_face_count": len(synthetic_faces),
        "synthetic_class_count": len(set(synthetic_tile_ids)),
        "known_same_match_synthetic_exclusion": KNOWN_HAND_SESSION_MATCH_GROUPS,
        "aggregate": {
            **aggregate,
            "synthetic_only_face_accuracy": ratio(
                aggregate["synthetic_only_face_correct"], face_total
            ),
            "real_first_face_accuracy": ratio(
                aggregate["real_first_face_correct"], face_total
            ),
            "synthetic_only_group_accuracy": ratio(
                aggregate["synthetic_only_group_correct"], group_total
            ),
            "real_first_group_accuracy": ratio(
                aggregate["real_first_group_correct"], group_total
            ),
        },
        "folds": folds,
        "evidence_role": "development_selection_only",
        "blind_validation": False,
        "blind_validation_blocker": (
            "concealed-template original-match lineage is incomplete outside the "
            "explicitly mapped older eight-hand source"
        ),
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
    parser.add_argument(
        "--source-registry",
        default="references/vision/2026-09-24/public_identity_source_groups.development.json",
    )
    parser.add_argument("--output")
    args = parser.parse_args()
    report = evaluate_public_meld_mobilenet_embedding(
        args.repository_root,
        args.dataset,
        args.calibration,
        args.source_registry,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
