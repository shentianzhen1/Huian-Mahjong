"""One-shot development evaluator for a measured opponent exposed meld.

The evaluator uses the existing geometry normalizer, a frozen MobileNetV3-Small
ImageNet embedding, and synthetic concealed-hand templates degraded to the
measured opponent source resolution. It is deliberately ranking-only:
MobileNet cosine scores are not calibrated to the Runtime 0.82 identity gate.
"""
from __future__ import annotations

import argparse
from itertools import permutations
import hashlib
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from PIL import Image

from workspace.vision.opponent_meld_domain_transfer import (
    load_opponent_meld_domain_profile,
    qualify_opponent_meld_domain_profile,
    simulate_opponent_source_resolution_loss,
)
from workspace.vision.concealed_template_match_lineage import (
    load_concealed_template_lineage,
    qualify_concealed_template_labels,
)
from workspace.vision.public_meld_face_segmentation import prepare_public_meld_faces
from workspace.vision.public_meld_group_identity_decoder import (
    rank_regular_public_meld_identity,
)
from workspace.vision.public_meld_mobilenet_embedding import (
    MODEL_NAME,
    _embed_images,
    _load_model,
    _mean_prototypes,
    _scores,
    _square_tile_canvas,
)
from workspace.vision.public_meld_synthetic_transfer import (
    MAX_HAND_TEMPLATES_PER_CLASS,
    render_self_meld_variants,
)
from workspace.vision.tiles_v0_1.labels import approved_labels
from workspace.vision.public_tile_detector import PublicGeometryCandidate


@dataclass(frozen=True)
class QuerySpec:
    review_id: str
    query_match_group: str
    strip_path: str
    strip_sha256: str
    frame_width: int
    frame_height: int
    source_frame_estimates: tuple[int, ...]


M123_QUERY = QuerySpec(
    review_id="opp_meld_14_m123",
    query_match_group="reviewed_recording_14",
    strip_path=(
        "references/vision/2026-10-01/opponent_meld_crops/"
        "opp_meld_14_m123_5frame_strip.webp"
    ),
    strip_sha256="d6122210ebb2f5c230ecb08ac35c205824495695341a938831ded2f156fe81f9",
    frame_width=71,
    frame_height=33,
    source_frame_estimates=(1726, 1728, 1730, 1732, 1734),
)
S456_QUERY = QuerySpec(
    review_id="opp_meld_0926_hand1_s456",
    query_match_group="reviewed_match_2026_09_26_first_hand",
    strip_path=(
        "references/vision/2026-10-01/opponent_meld_crops/"
        "opp_meld_0926_hand1_s456_5frame_strip.webp"
    ),
    strip_sha256="e49a817e836a890166cbb95b18dbeb0a6c66f242c7c3f7bf1f2849d71e7ef7dc",
    frame_width=71,
    frame_height=33,
    source_frame_estimates=(4904, 4908, 4913, 4918, 4923),
)
QUERY_SPECS = {"m123": M123_QUERY, "s456": S456_QUERY}

# Backward-compatible aliases for the original M123 evaluator contract.
REVIEW_ID = M123_QUERY.review_id
QUERY_MATCH_GROUP = M123_QUERY.query_match_group
DEFAULT_STRIP = M123_QUERY.strip_path
DEFAULT_STRIP_SHA256 = M123_QUERY.strip_sha256
FRAME_WIDTH = M123_QUERY.frame_width
FRAME_HEIGHT = M123_QUERY.frame_height
SOURCE_FRAME_ESTIMATES = M123_QUERY.source_frame_estimates
RUNTIME_IDENTITY_THRESHOLD = 0.82


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _topk(scores: Mapping[str, float], count: int) -> list[tuple[str, float]]:
    return [
        (tile_id, float(score))
        for tile_id, score in sorted(
            scores.items(), key=lambda row: (-row[1], row[0])
        )[:count]
    ]


def _unordered_top1_exact(
    score_rows: Sequence[Mapping[str, float]],
    expected_tiles: Sequence[str],
) -> bool:
    if len(score_rows) != len(expected_tiles):
        return False
    winners = [
        row[0][0]
        for row in (_topk(scores, 1) for scores in score_rows)
        if row
    ]
    return (
        len(winners) == len(expected_tiles)
        and sorted(winners) == sorted(expected_tiles)
    )


def _unordered_topk_covers_expected(
    score_rows: Sequence[Mapping[str, float]],
    expected_tiles: Sequence[str],
    *,
    count: int,
) -> bool:
    """Check expected meld coverage without assuming left-to-right UI order."""
    if len(score_rows) != len(expected_tiles):
        return False
    top_sets = [
        set(tile for tile, _ in _topk(scores, count))
        for scores in score_rows
    ]
    assignments = set(permutations(tuple(expected_tiles)))
    return any(
        all(
            assignment[index] in top_sets[index]
            for index in range(len(top_sets))
        )
        for assignment in assignments
    )


def _mean_score_rows(
    frames: Sequence[Sequence[Mapping[str, float]]],
) -> list[dict[str, float]]:
    if not frames:
        raise ValueError(
            "multi-frame score aggregation requires at least one frame"
        )
    face_count = len(frames[0])
    if face_count != 3 or any(
        len(frame) != face_count for frame in frames
    ):
        raise ValueError(
            "expected exactly three stable face slots per frame"
        )
    result: list[dict[str, float]] = []
    for face_index in range(face_count):
        classes = set(frames[0][face_index])
        if any(
            set(frame[face_index]) != classes for frame in frames[1:]
        ):
            raise ValueError(
                "prototype class set drifted across frames"
            )
        result.append(
            {
                tile_id: sum(
                    float(frame[face_index][tile_id])
                    for frame in frames
                )
                / len(frames)
                for tile_id in sorted(classes)
            }
        )
    return result


def _find_review_row(queue: dict[str, Any]) -> dict[str, Any]:
    matches = [
        row
        for row in queue.get("items", ())
        if isinstance(row, dict)
        and row.get("review_id") == REVIEW_ID
    ]
    if len(matches) != 1:
        raise ValueError(
            "expected exactly one locked opponent review row"
        )
    return matches[0]


def _load_query_frames(
    strip_path: Path,
    expected_count: int,
) -> list[Image.Image]:
    if _sha256(strip_path) != DEFAULT_STRIP_SHA256:
        raise ValueError(
            "opponent five-frame strip SHA256 mismatch"
        )
    with Image.open(strip_path) as source:
        strip = source.convert("RGB")
    if strip.size != (
        FRAME_WIDTH,
        FRAME_HEIGHT * expected_count,
    ):
        raise ValueError(
            "opponent five-frame strip dimensions drifted"
        )
    return [
        strip.crop(
            (
                0,
                index * FRAME_HEIGHT,
                FRAME_WIDTH,
                (index + 1) * FRAME_HEIGHT,
            )
        )
        for index in range(expected_count)
    ]


def _prepare_query_faces(
    frames: Sequence[Image.Image],
) -> list[list[Any]]:
    prepared_frames: list[list[Any]] = []
    for index, frame in enumerate(frames):
        candidate = PublicGeometryCandidate(
            pixel_bbox=(0, 0, FRAME_WIDTH, FRAME_HEIGHT),
            normalized_bbox=(0.0, 0.0, 1.0, 1.0),
            geometry_kind="top_group",
            confidence=1.0,
            fill_ratio=1.0,
            frame=SOURCE_FRAME_ESTIMATES[index],
            session=REVIEW_ID,
        )
        prepared = prepare_public_meld_faces(
            frame,
            candidate,
        )
        if (
            prepared.geometry.stack_state != "FLAT"
            or len(prepared.face_images) != 3
        ):
            raise ValueError(
                "tracked opponent frame is no longer "
                "classifier-ready FLAT geometry"
            )
        prepared_frames.append(
            list(prepared.face_images)
        )
    return prepared_frames


def _balance_lineage_qualified_hand_labels(
    labels: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in labels:
        tile_id = row.get("tile_id")
        image_path = row.get("image")
        if not isinstance(tile_id, str) or not isinstance(image_path, str):
            continue
        grouped.setdefault(tile_id, []).append(row)

    selected: list[dict[str, Any]] = []
    for tile_id in sorted(grouped):
        rows = sorted(
            grouped[tile_id],
            key=lambda row: (
                str(row.get("_original_match_group") or ""),
                str(row.get("source_session") or ""),
                str(row.get("image") or ""),
                int(row.get("source_frame") or -1),
            ),
        )
        chosen: list[dict[str, Any]] = []
        used_groups: set[str] = set()
        for row in rows:
            group = str(row.get("_original_match_group") or "")
            if group and group in used_groups:
                continue
            chosen.append(row)
            if group:
                used_groups.add(group)
            if len(chosen) >= MAX_HAND_TEMPLATES_PER_CLASS:
                break
        if len(chosen) < MAX_HAND_TEMPLATES_PER_CLASS:
            for row in rows:
                if row in chosen:
                    continue
                chosen.append(row)
                if len(chosen) >= MAX_HAND_TEMPLATES_PER_CLASS:
                    break
        selected.extend(chosen)
    return selected


def _synthetic_opponent_domain_bank(
    dataset_root: Path,
    lineage_registry: Path,
    profile: Any,
) -> tuple[list[str], list[Any], dict[str, Any]]:
    lineage = load_concealed_template_lineage(lineage_registry)
    candidate_labels = [
        row
        for row in approved_labels(dataset_root)
        if row.get("region") == "hand_region"
        and not row.get("gold_skin_only")
    ]
    qualified_labels, lineage_info = qualify_concealed_template_labels(
        candidate_labels,
        lineage,
        query_match_group=QUERY_MATCH_GROUP,
    )
    labels = _balance_lineage_qualified_hand_labels(qualified_labels)

    tile_ids: list[str] = []
    images: list[Any] = []
    used_label_count = 0

    for label in labels:
        tile_id = label.get("tile_id")
        image_value = label.get("image")
        if (
            not isinstance(tile_id, str)
            or not isinstance(image_value, str)
        ):
            continue

        path = (dataset_root / image_value).resolve()
        if dataset_root.resolve() not in path.parents:
            raise ValueError(
                "hand template path escapes dataset root"
            )
        with Image.open(path) as original:
            image = original.convert("RGB")
        used_label_count += 1
        for variant in render_self_meld_variants(image):
            degraded = (
                simulate_opponent_source_resolution_loss(
                    variant,
                    profile,
                )
            )
            tile_ids.append(tile_id)
            images.append(
                _square_tile_canvas(degraded)
            )

    return tile_ids, images, {
        "candidate_hand_label_count": len(candidate_labels),
        "lineage_qualified_hand_label_count": len(qualified_labels),
        "balanced_hand_label_count": len(labels),
        "used_hand_label_count": used_label_count,
        "synthetic_variant_count": len(images),
        "synthetic_class_count": len(set(tile_ids)),
        "lineage": lineage_info,
    }

def _frame_summary(
    score_rows: Sequence[Mapping[str, float]],
    expected_tiles: Sequence[str],
) -> dict[str, Any]:
    legal = rank_regular_public_meld_identity(
        score_rows
    )
    legal_correct = (
        legal.top_tiles is not None
        and sorted(legal.top_tiles)
        == sorted(expected_tiles)
    )
    return {
        "face_top1": [
            {
                "tile": rows[0][0],
                "score": round(rows[0][1], 8),
            }
            if rows
            else None
            for rows in (
                _topk(scores, 1)
                for scores in score_rows
            )
        ],
        "face_top3": [
            [
                {
                    "tile": tile,
                    "score": round(score, 8),
                }
                for tile, score in _topk(scores, 3)
            ]
            for scores in score_rows
        ],
        "raw_unordered_top1_exact": (
            _unordered_top1_exact(
                score_rows,
                expected_tiles,
            )
        ),
        "unordered_top3_expected_coverage": (
            _unordered_topk_covers_expected(
                score_rows,
                expected_tiles,
                count=3,
            )
        ),
        "legal_group": legal.to_dict(),
        "legal_group_correct": legal_correct,
    }


def evaluate_opponent_public_meld_mobilenet(
    repository_root: str | Path = ".",
    dataset_root: str | Path = (
        "dataset/tiles_runtime_v0_2"
    ),
    profile_path: str | Path = (
        "references/vision/2026-10-01/"
        "opponent_meld_domain_profile_v0_1.json"
    ),
    queue_path: str | Path = (
        "references/vision/2026-10-01/"
        "opponent_public_meld_review_queue_v0_1.json"
    ),
    template_lineage_path: str | Path = (
        "references/vision/2026-10-01/"
        "concealed_template_match_lineage.development.json"
    ),
    strip_path: str | Path = DEFAULT_STRIP,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    dataset = (root / dataset_root).resolve()
    profile_file = (root / profile_path).resolve()
    queue_file = (root / queue_path).resolve()
    lineage_file = (
        root / template_lineage_path
    ).resolve()
    strip_file = (root / strip_path).resolve()

    for path in (
        dataset,
        profile_file,
        queue_file,
        lineage_file,
        strip_file,
    ):
        if root != path and root not in path.parents:
            raise ValueError(
                "evaluation path escapes repository root"
            )

    profile = load_opponent_meld_domain_profile(
        profile_file
    )
    queue = json.loads(
        queue_file.read_text(encoding="utf-8")
    )
    qualification = (
        qualify_opponent_meld_domain_profile(
            profile,
            queue,
        )
    )
    if not qualification["qualified"]:
        raise ValueError(
            "opponent domain profile is not "
            "source-qualified"
        )
    review = _find_review_row(queue)
    expected_tiles = tuple(
        review["expected_tiles"]
    )
    stable_count = int(
        review["stable_measurement_crop_count"]
    )
    if stable_count != len(SOURCE_FRAME_ESTIMATES):
        raise ValueError(
            "stable opponent frame count drifted"
        )

    frames = _load_query_frames(
        strip_file,
        stable_count,
    )
    prepared_frames = _prepare_query_faces(frames)

    (
        synthetic_tile_ids,
        synthetic_images,
        bank_info,
    ) = _synthetic_opponent_domain_bank(
        dataset,
        lineage_file,
        profile,
    )
    if not synthetic_images:
        raise ValueError(
            "opponent-domain synthetic template bank "
            "is empty"
        )
    missing_lineage_expected = sorted(
        set(expected_tiles) - set(synthetic_tile_ids)
    )
    if missing_lineage_expected:
        raise ValueError(
            "lineage-qualified opponent template bank "
            "is missing expected classes: "
            + ",".join(missing_lineage_expected)
        )

    model, transform, weight_name = _load_model()
    synthetic_embeddings = _embed_images(
        synthetic_images,
        model,
        transform,
    )
    prototypes = _mean_prototypes(
        synthetic_tile_ids,
        synthetic_embeddings,
    )
    missing_expected = sorted(
        set(expected_tiles) - set(prototypes)
    )
    if missing_expected:
        raise ValueError(
            "expected opponent tiles missing from "
            "synthetic prototypes: "
            + ",".join(missing_expected)
        )

    query_images = [
        _square_tile_canvas(face)
        for frame_faces in prepared_frames
        for face in frame_faces
    ]
    query_embeddings = _embed_images(
        query_images,
        model,
        transform,
    )

    all_frame_scores: list[
        list[dict[str, float]]
    ] = []
    cursor = 0
    for _ in prepared_frames:
        frame_rows: list[dict[str, float]] = []
        for _face_index in range(3):
            frame_rows.append(
                _scores(
                    query_embeddings[cursor],
                    prototypes,
                )
            )
            cursor += 1
        all_frame_scores.append(frame_rows)

    frames_report: list[dict[str, Any]] = []
    for frame_index, score_rows in enumerate(
        all_frame_scores
    ):
        frames_report.append(
            {
                "source_frame_estimate": (
                    SOURCE_FRAME_ESTIMATES[
                        frame_index
                    ]
                ),
                **_frame_summary(
                    score_rows,
                    expected_tiles,
                ),
            }
        )

    aggregate_scores = _mean_score_rows(
        all_frame_scores
    )
    aggregate_report = _frame_summary(
        aggregate_scores,
        expected_tiles,
    )

    import torch
    import torchvision

    return {
        "schema_version": (
            "opponent_public_meld_mobilenet_v0_1"
        ),
        "date": "2026-10-01",
        "issue": 69,
        "review_id": REVIEW_ID,
        "query_match_group": QUERY_MATCH_GROUP,
        "expected_tiles": list(expected_tiles),
        "query": {
            "stable_frame_count": stable_count,
            "source_frame_estimates": list(
                SOURCE_FRAME_ESTIMATES
            ),
            "public_strip_path": (
                Path(strip_path).as_posix()
            ),
            "public_strip_sha256": (
                DEFAULT_STRIP_SHA256
            ),
            "frame_size_px": [
                FRAME_WIDTH,
                FRAME_HEIGHT,
            ],
            "prepared_face_observation_count": (
                len(query_images)
            ),
            "human_truth_scope": (
                "group_identity_only_no_left_to_right_"
                "truth_assumed"
            ),
        },
        "opponent_domain_profile": {
            "status": profile.status,
            "measured_source_face_size_px": list(
                profile.measured_source_face_size_px
                or ()
            ),
            "qualification": qualification,
        },
        "synthetic_bank": bank_info,
        "model": {
            "name": MODEL_NAME,
            "weights": weight_name,
            "fine_tuned": False,
            "torch_version": torch.__version__,
            "torchvision_version": (
                torchvision.__version__
            ),
            "prototype_class_count": len(
                prototypes
            ),
        },
        "frames": frames_report,
        "frame_metrics": {
            "frame_count": len(frames_report),
            "raw_unordered_top1_exact_count": sum(
                bool(
                    row[
                        "raw_unordered_top1_exact"
                    ]
                )
                for row in frames_report
            ),
            "unordered_top3_expected_coverage_count": sum(
                bool(
                    row[
                        "unordered_top3_expected_coverage"
                    ]
                )
                for row in frames_report
            ),
            "legal_group_top1_correct_count": sum(
                bool(row["legal_group_correct"])
                for row in frames_report
            ),
        },
        "multi_frame_mean_scores": (
            aggregate_report
        ),
        "evidence_role": (
            "development_measurement_only"
        ),
        "blind_validation": False,
        "blind_validation_blockers": [
            (
                "the same reviewed opponent match "
                "supplied the source-resolution "
                "measurement"
            ),
            (
                "concealed hand templates without "
                "exact-SHA original-match lineage "
                "are excluded from the bank"
            ),
            (
                "only one opponent match group is "
                "measured in this batch"
            ),
        ],
        "independent_opponent_match_group_count": 1,
        "mobilenet_acceptance_threshold": None,
        "identity_runtime_status": "UNKNOWN",
        "runtime_identity_threshold_unchanged": (
            RUNTIME_IDENTITY_THRESHOLD
        ),
        "changes_runtime_behavior": False,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__
    )
    parser.add_argument(
        "--repository-root",
        default=".",
    )
    parser.add_argument(
        "--dataset",
        default="dataset/tiles_runtime_v0_2",
    )
    parser.add_argument(
        "--profile",
        default=(
            "references/vision/2026-10-01/"
            "opponent_meld_domain_profile_v0_1.json"
        ),
    )
    parser.add_argument(
        "--queue",
        default=(
            "references/vision/2026-10-01/"
            "opponent_public_meld_review_queue_v0_1.json"
        ),
    )
    parser.add_argument(
        "--template-lineage",
        default=(
            "references/vision/2026-10-01/"
            "concealed_template_match_lineage.development.json"
        ),
    )
    parser.add_argument(
        "--strip",
        default=DEFAULT_STRIP,
    )
    parser.add_argument("--output")
    args = parser.parse_args()
    report = (
        evaluate_opponent_public_meld_mobilenet(
            args.repository_root,
            args.dataset,
            args.profile,
            args.queue,
            args.template_lineage,
            args.strip,
        )
    )
    rendered = json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
    )
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        output.write_text(
            rendered + "\n",
            encoding="utf-8",
        )
    print(rendered)


if __name__ == "__main__":
    main()
