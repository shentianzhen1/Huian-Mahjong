"""Development-only probe: real public-meld prototypes for opponent S456.

Compares the frozen lineage-qualified synthetic concealed-template bank with a
real-public-first bank. Reviewed real public-meld faces are allowed only from
original match groups different from the opponent query match. This is a
diagnostic/selection experiment only and cannot change Runtime/Hint/Executor.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

from workspace.vision.opponent_meld_domain_transfer import (
    load_opponent_meld_domain_profile,
)
from workspace.vision.opponent_public_meld_mobilenet import (
    RUNTIME_IDENTITY_THRESHOLD,
    S456_QUERY,
    _frame_summary,
    _load_query_frames,
    _mean_score_rows,
    _prepare_query_faces,
    _synthetic_opponent_domain_bank,
)
from workspace.vision.public_meld_mobilenet_embedding import (
    MODEL_NAME,
    _embed_images,
    _load_model,
    _load_real_faces,
    _mean_prototypes,
    _scores,
    _square_tile_canvas,
)


def _evaluate(
    query_embeddings: Any,
    frame_count: int,
    prototypes: Mapping[str, Any],
    expected_tiles: tuple[str, ...],
) -> dict[str, Any]:
    all_frame_scores: list[list[dict[str, float]]] = []
    cursor = 0
    for _ in range(frame_count):
        rows: list[dict[str, float]] = []
        for _face in range(3):
            rows.append(_scores(query_embeddings[cursor], dict(prototypes)))
            cursor += 1
        all_frame_scores.append(rows)

    frames = [
        _frame_summary(score_rows, expected_tiles)
        for score_rows in all_frame_scores
    ]
    aggregate = _frame_summary(
        _mean_score_rows(all_frame_scores),
        expected_tiles,
    )
    return {
        "frame_metrics": {
            "frame_count": len(frames),
            "raw_unordered_top1_exact_count": sum(
                bool(row["raw_unordered_top1_exact"]) for row in frames
            ),
            "unordered_top3_expected_coverage_count": sum(
                bool(row["unordered_top3_expected_coverage"]) for row in frames
            ),
            "legal_group_top1_correct_count": sum(
                bool(row["legal_group_correct"]) for row in frames
            ),
        },
        "multi_frame_mean_scores": aggregate,
    }


def run(repository_root: str | Path = ".") -> dict[str, Any]:
    root = Path(repository_root).resolve()
    dataset = root / "dataset/tiles_runtime_v0_2"
    profile = load_opponent_meld_domain_profile(
        root / "references/vision/2026-10-01/opponent_meld_domain_profile_v0_1.json"
    )
    lineage = (
        root
        / "references/vision/2026-10-01/"
        "concealed_template_match_lineage.development.json"
    )
    calibration = json.loads(
        (
            root
            / "references/vision/2026-09-22/"
            "public_detector_calibration_v0_1.json"
        ).read_text(encoding="utf-8")
    )
    source_registry = (
        root
        / "references/vision/2026-09-24/"
        "public_identity_source_groups.development.json"
    )

    frames = _load_query_frames(
        root / S456_QUERY.strip_path,
        len(S456_QUERY.source_frame_estimates),
        S456_QUERY,
    )
    prepared = _prepare_query_faces(frames, S456_QUERY)
    expected_tiles = ("S4", "S5", "S6")

    synthetic_ids, synthetic_images, synthetic_info = (
        _synthetic_opponent_domain_bank(
            dataset,
            lineage,
            profile,
            S456_QUERY.query_match_group,
        )
    )

    real_faces, real_groups = _load_real_faces(
        root,
        calibration,
        source_registry,
    )
    eligible_real = [
        row for row in real_faces
        if row.match_group != S456_QUERY.query_match_group
    ]
    if not eligible_real:
        raise ValueError("real public-meld reference bank is empty")

    model, transform, weight_name = _load_model()
    synthetic_embeddings = _embed_images(
        synthetic_images, model, transform
    )
    synthetic_prototypes = _mean_prototypes(
        synthetic_ids, synthetic_embeddings
    )

    real_embeddings = _embed_images(
        [row.image for row in eligible_real], model, transform
    )
    real_ids = [row.tile_id for row in eligible_real]
    real_prototypes = _mean_prototypes(real_ids, real_embeddings)

    real_first = dict(synthetic_prototypes)
    real_first.update(real_prototypes)

    query_images = [
        _square_tile_canvas(face)
        for frame_faces in prepared
        for face in frame_faces
    ]
    query_embeddings = _embed_images(
        query_images, model, transform
    )

    coverage: dict[str, dict[str, Any]] = {}
    for tile in expected_tiles:
        tile_rows = [row for row in eligible_real if row.tile_id == tile]
        groups: dict[str, int] = defaultdict(int)
        for row in tile_rows:
            groups[row.match_group] += 1
        coverage[tile] = {
            "real_face_count": len(tile_rows),
            "independent_match_group_count": len(groups),
            "labels_by_match_group": dict(sorted(groups.items())),
            "real_prototype_available": tile in real_prototypes,
        }

    synthetic_result = _evaluate(
        query_embeddings,
        len(prepared),
        synthetic_prototypes,
        expected_tiles,
    )
    real_first_result = _evaluate(
        query_embeddings,
        len(prepared),
        real_first,
        expected_tiles,
    )

    return {
        "schema_version": "opponent_meld_real_public_probe_v0_1",
        "date": "2026-10-01",
        "issue": 69,
        "review_id": S456_QUERY.review_id,
        "query_match_group": S456_QUERY.query_match_group,
        "query_public_strip_sha256": S456_QUERY.strip_sha256,
        "expected_tiles": list(expected_tiles),
        "reference_policy": (
            "real_public_meld_prototype_from_other_match_groups_first_"
            "otherwise_lineage_qualified_synthetic_fallback"
        ),
        "real_reference_query_match_excluded": True,
        "real_reference_coverage": coverage,
        "real_reference_face_count": len(eligible_real),
        "real_reference_group_count": len({
            row.sample_id for row in eligible_real
        }),
        "real_reference_match_groups": sorted({
            row.match_group for row in eligible_real
        }),
        "synthetic_bank": synthetic_info,
        "model": {
            "name": MODEL_NAME,
            "weights": weight_name,
            "fine_tuned": False,
            "synthetic_prototype_class_count": len(synthetic_prototypes),
            "real_prototype_class_count": len(real_prototypes),
            "real_first_prototype_class_count": len(real_first),
        },
        "synthetic_only": synthetic_result,
        "real_public_first": real_first_result,
        "interpretation_role": (
            "diagnose whether cross-match real public-meld pixels reduce "
            "the opponent-domain gap; not a promotion gate"
        ),
        "evidence_role": "development_selection_only",
        "blind_validation": False,
        "mobilenet_acceptance_threshold": None,
        "identity_runtime_status": "UNKNOWN",
        "runtime_identity_threshold_unchanged": RUNTIME_IDENTITY_THRESHOLD,
        "changes_runtime_behavior": False,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
        "reviewed_real_groups_seen_during_selection": len(real_groups),
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = run(args.repository_root)
    Path(args.output).write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    compact = {
        "coverage": report["real_reference_coverage"],
        "synthetic_only": report["synthetic_only"]["frame_metrics"],
        "synthetic_multi": report["synthetic_only"]["multi_frame_mean_scores"][
            "legal_group"
        ],
        "real_public_first": report["real_public_first"]["frame_metrics"],
        "real_public_multi": report["real_public_first"]["multi_frame_mean_scores"][
            "legal_group"
        ],
    }
    print(json.dumps(compact, sort_keys=True))


if __name__ == "__main__":
    main()
