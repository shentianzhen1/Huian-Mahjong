"""Development-only late fusion for real and synthetic public-meld SIFT.

This small A/B keeps the existing geometry and SIFT implementations unchanged.
It asks one narrow question on the same seven reviewed player-side regular meld
groups used by the synthetic-transfer experiment:

Does combining a leave-one-group-out real-meld SIFT branch with the synthetic
hand-to-meld SIFT branch improve identity ranking after Mahjong-valid group
decoding?

Important evidence boundary:
- the reviewed target groups are development data, not a blind holdout;
- the real branch excludes the exact target group but may still contain another
  group from the same original match;
- the fusion rule is fixed before looking at this report;
- no Runtime, Hint, Executor, production threshold, or frozen SIFT candidate is
  changed by this experiment.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Mapping

from PIL import Image

from workspace.vision.public_meld_face_segmentation import prepare_public_meld_faces
from workspace.vision.public_meld_group_identity_decoder import (
    rank_regular_public_meld_identity,
)
from workspace.vision.public_meld_identity_sift import (
    _descriptor_similarity,
    _sift_descriptors,
)
from workspace.vision.public_meld_synthetic_transfer import (
    _build_hand_template_bank,
    _canonical_face,
    _class_scores as _synthetic_class_scores,
    _pixel_bbox,
    _regular_player_meld_samples,
    _top1,
)
from workspace.vision.public_tile_detector import PublicGeometryCandidate


@dataclass(frozen=True)
class RealMeldTemplateRecord:
    sample_id: str
    tile_id: str
    source_session: str
    source_sha256: str
    descriptors: Any


def _prepared_faces(root: Path, sample: Mapping[str, Any]) -> tuple[Any, ...]:
    image_path = (root / str(sample["image_path"])).resolve()
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
    return tuple(prepared.face_images)


def _build_real_template_bank(
    root: Path,
    samples: list[dict[str, Any]],
) -> tuple[RealMeldTemplateRecord, ...]:
    records: list[RealMeldTemplateRecord] = []
    for sample in samples:
        faces = _prepared_faces(root, sample)
        expected = tuple(str(tile) for tile in sample["expected_tiles"])
        if len(faces) != 3 or len(expected) != 3:
            continue
        for face, tile_id in zip(faces, expected):
            descriptors = _sift_descriptors(face)
            if descriptors is None:
                continue
            records.append(
                RealMeldTemplateRecord(
                    sample_id=str(sample["sample_id"]),
                    tile_id=tile_id,
                    source_session=str(sample["source_session"]),
                    source_sha256=str(sample["source_sha256"]),
                    descriptors=descriptors,
                )
            )
    return tuple(records)


def _real_class_scores(
    query_descriptors: Any,
    bank: tuple[RealMeldTemplateRecord, ...],
    *,
    exclude_sample_id: str,
) -> dict[str, float]:
    """Best SIFT score by class, excluding the exact reviewed target group."""
    scores: dict[str, float] = {}
    for record in bank:
        if record.sample_id == exclude_sample_id:
            continue
        score = _descriptor_similarity(query_descriptors, record.descriptors)
        if score is None:
            continue
        scores[record.tile_id] = max(
            scores.get(record.tile_id, float("-inf")),
            float(score),
        )
    return scores


def _rank_percentiles(scores: Mapping[str, float]) -> dict[str, float]:
    """Map one backend's scores to deterministic [0, 1] rank percentiles.

    Fusion should not assume that real-meld and synthetic SIFT similarities have
    identical numeric calibration. Ranking within each backend first avoids
    introducing a tuned scale factor in this small selection experiment.
    """
    rows = [
        (str(tile_id), float(score))
        for tile_id, score in scores.items()
        if (
            not isinstance(score, bool)
            and isinstance(score, (int, float))
            and math.isfinite(float(score))
        )
    ]
    rows.sort(key=lambda row: (-row[1], row[0]))
    if not rows:
        return {}
    if len(rows) == 1:
        return {rows[0][0]: 1.0}
    denominator = float(len(rows) - 1)
    return {
        tile_id: 1.0 - (index / denominator)
        for index, (tile_id, _score) in enumerate(rows)
    }


def fuse_rank_percentile_scores(
    real_scores: Mapping[str, float],
    synthetic_scores: Mapping[str, float],
) -> dict[str, float]:
    """Equal late fusion after per-backend rank normalization.

    A class present in both branches receives the arithmetic mean. A class
    present in only one branch keeps that branch's normalized rank instead of
    being treated as negative evidence; missing class coverage is unknown, not
    a vote against the class.
    """
    real = _rank_percentiles(real_scores)
    synthetic = _rank_percentiles(synthetic_scores)
    fused: dict[str, float] = {}
    for tile_id in sorted(set(real) | set(synthetic)):
        values = [
            branch[tile_id]
            for branch in (real, synthetic)
            if tile_id in branch
        ]
        if values:
            fused[tile_id] = float(sum(values) / len(values))
    return fused


def evaluate_public_meld_sift_fusion(
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
    real_bank = _build_real_template_bank(root, samples)
    synthetic_bank = _build_hand_template_bank(dataset)
    if not real_bank:
        raise ValueError("real public-meld development bank is empty")
    if not synthetic_bank:
        raise ValueError("synthetic hand-template bank is empty")

    face_rows: list[dict[str, Any]] = []
    group_rows: list[dict[str, Any]] = []

    for sample in samples:
        sample_id = str(sample["sample_id"])
        faces = _prepared_faces(root, sample)
        expected_tiles = tuple(str(tile) for tile in sample["expected_tiles"])
        if len(faces) != 3:
            group_rows.append(
                {
                    "sample_id": sample_id,
                    "expected_tiles": list(expected_tiles),
                    "prepared_face_count": len(faces),
                    "real_group_correct": False,
                    "synthetic_group_correct": False,
                    "fusion_group_correct": False,
                    "reason": "not_three_classifier_ready_faces",
                }
            )
            continue

        real_face_scores: list[dict[str, float]] = []
        synthetic_face_scores: list[dict[str, float]] = []
        fusion_face_scores: list[dict[str, float]] = []

        for face_index, (face, expected_tile) in enumerate(
            zip(faces, expected_tiles)
        ):
            real_query = _sift_descriptors(face)
            synthetic_query = _sift_descriptors(_canonical_face(face))
            real_scores = (
                _real_class_scores(
                    real_query,
                    real_bank,
                    exclude_sample_id=sample_id,
                )
                if real_query is not None
                else {}
            )
            synthetic_scores = (
                _synthetic_class_scores(
                    synthetic_query,
                    synthetic_bank,
                    synthetic=True,
                )
                if synthetic_query is not None
                else {}
            )
            fusion_scores = fuse_rank_percentile_scores(
                real_scores,
                synthetic_scores,
            )

            real_tile, real_score = _top1(real_scores)
            synthetic_tile, synthetic_score = _top1(synthetic_scores)
            fusion_tile, fusion_score = _top1(fusion_scores)

            real_face_scores.append(real_scores)
            synthetic_face_scores.append(synthetic_scores)
            fusion_face_scores.append(fusion_scores)
            face_rows.append(
                {
                    "sample_id": sample_id,
                    "face_index": face_index,
                    "expected_tile": expected_tile,
                    "real_top1": real_tile,
                    "real_score": (
                        round(real_score, 8) if real_score is not None else None
                    ),
                    "real_correct": real_tile == expected_tile,
                    "synthetic_top1": synthetic_tile,
                    "synthetic_score": (
                        round(synthetic_score, 8)
                        if synthetic_score is not None
                        else None
                    ),
                    "synthetic_correct": synthetic_tile == expected_tile,
                    "fusion_top1": fusion_tile,
                    "fusion_score": (
                        round(fusion_score, 8) if fusion_score is not None else None
                    ),
                    "fusion_correct": fusion_tile == expected_tile,
                }
            )

        real_group = rank_regular_public_meld_identity(real_face_scores)
        synthetic_group = rank_regular_public_meld_identity(synthetic_face_scores)
        fusion_group = rank_regular_public_meld_identity(fusion_face_scores)
        expected_sorted = sorted(expected_tiles)

        def group_correct(ranking: Any) -> bool:
            return (
                ranking.top_tiles is not None
                and sorted(ranking.top_tiles) == expected_sorted
            )

        group_rows.append(
            {
                "sample_id": sample_id,
                "expected_tiles": list(expected_tiles),
                "prepared_face_count": 3,
                "real_group_tiles": (
                    list(real_group.top_tiles)
                    if real_group.top_tiles is not None
                    else None
                ),
                "real_group_correct": group_correct(real_group),
                "synthetic_group_tiles": (
                    list(synthetic_group.top_tiles)
                    if synthetic_group.top_tiles is not None
                    else None
                ),
                "synthetic_group_correct": group_correct(synthetic_group),
                "fusion_group_tiles": (
                    list(fusion_group.top_tiles)
                    if fusion_group.top_tiles is not None
                    else None
                ),
                "fusion_group_correct": group_correct(fusion_group),
            }
        )

    scorable_groups = [
        row for row in group_rows if row.get("prepared_face_count") == 3
    ]
    face_count = len(face_rows)
    group_count = len(scorable_groups)

    def face_summary(prefix: str) -> dict[str, Any]:
        correct = sum(bool(row[f"{prefix}_correct"]) for row in face_rows)
        return {
            "face_top1_correct": correct,
            "face_top1_total": face_count,
            "face_top1_accuracy": (
                round(correct / face_count, 6) if face_count else None
            ),
        }

    def group_summary(prefix: str) -> dict[str, Any]:
        correct = sum(bool(row[f"{prefix}_group_correct"]) for row in scorable_groups)
        return {
            "group_top1_correct": correct,
            "group_top1_total": group_count,
            "group_top1_accuracy": (
                round(correct / group_count, 6) if group_count else None
            ),
        }

    real_summary = {
        "name": "real_public_meld_sift_leave_one_group_out",
        **face_summary("real"),
        **group_summary("real"),
    }
    synthetic_summary = {
        "name": "synthetic_hand_to_meld_sift",
        **face_summary("synthetic"),
        **group_summary("synthetic"),
    }
    fusion_summary = {
        "name": "equal_rank_percentile_late_fusion_plus_legal_group_decoder",
        **face_summary("fusion"),
        **group_summary("fusion"),
    }

    return {
        "schema_version": "public_meld_sift_fusion_v0_1",
        "method": "real_leave_one_group_out_plus_synthetic_equal_rank_percentile_fusion",
        "fusion_policy": {
            "score_normalization": "per_backend_rank_percentile",
            "branch_weights": {"real": 0.5, "synthetic": 0.5},
            "missing_branch_class": "use_available_branch_only",
            "parameter_tuning_on_this_batch": False,
        },
        "real_template_face_count": len(real_bank),
        "synthetic_hand_template_count": len(synthetic_bank),
        "target_group_count": len(samples),
        "scored_group_count": group_count,
        "scored_face_count": face_count,
        "real": real_summary,
        "synthetic": synthetic_summary,
        "fusion": fusion_summary,
        "fusion_face_delta_vs_real": (
            round(
                fusion_summary["face_top1_accuracy"]
                - real_summary["face_top1_accuracy"],
                6,
            )
            if (
                fusion_summary["face_top1_accuracy"] is not None
                and real_summary["face_top1_accuracy"] is not None
            )
            else None
        ),
        "fusion_group_delta_vs_real": (
            round(
                fusion_summary["group_top1_accuracy"]
                - real_summary["group_top1_accuracy"],
                6,
            )
            if (
                fusion_summary["group_top1_accuracy"] is not None
                and real_summary["group_top1_accuracy"] is not None
            )
            else None
        ),
        "fusion_face_delta_vs_synthetic": (
            round(
                fusion_summary["face_top1_accuracy"]
                - synthetic_summary["face_top1_accuracy"],
                6,
            )
            if (
                fusion_summary["face_top1_accuracy"] is not None
                and synthetic_summary["face_top1_accuracy"] is not None
            )
            else None
        ),
        "fusion_group_delta_vs_synthetic": (
            round(
                fusion_summary["group_top1_accuracy"]
                - synthetic_summary["group_top1_accuracy"],
                6,
            )
            if (
                fusion_summary["group_top1_accuracy"] is not None
                and synthetic_summary["group_top1_accuracy"] is not None
            )
            else None
        ),
        "faces": face_rows,
        "groups": group_rows,
        "evidence_role": "development_selection_only",
        "blind_validation": False,
        "real_branch_source_disjoint_by_original_match": False,
        "real_branch_exact_target_group_excluded": True,
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
        default=(
            "references/vision/2026-09-22/"
            "public_detector_calibration_v0_1.json"
        ),
    )
    parser.add_argument("--output")
    args = parser.parse_args()
    report = evaluate_public_meld_sift_fusion(
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
