"""Development-only S456 public-meld split-boundary sensitivity diagnostic.

This module intentionally does not change the canonical splitter or Runtime.
It reuses the frozen opponent MobileNet evaluator and perturbs the two
normalized FLAT-row split boundaries to distinguish segmentation sensitivity
from the remaining opponent-domain transfer gap.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from workspace.vision.opponent_public_meld_mobilenet import (
    RUNTIME_IDENTITY_THRESHOLD,
    S456_QUERY,
    _load_query_frames,
    _mean_score_rows,
    _synthetic_opponent_domain_bank,
)
from workspace.vision.opponent_meld_domain_transfer import (
    load_opponent_meld_domain_profile,
)
from workspace.vision.public_meld_geometry_normalization import (
    normalize_public_meld_crop,
)
from workspace.vision.public_meld_group_identity_decoder import (
    rank_regular_public_meld_identity,
)
from workspace.vision.public_meld_mobilenet_embedding import (
    _embed_images,
    _load_model,
    _mean_prototypes,
    _scores,
    _square_tile_canvas,
)
from workspace.vision.public_tile_detector import PublicGeometryCandidate


def _candidate_faces(image: Any, frame: int, d1: int, d2: int) -> list[Any]:
    candidate = PublicGeometryCandidate(
        pixel_bbox=(0, 0, S456_QUERY.frame_width, S456_QUERY.frame_height),
        normalized_bbox=(0.0, 0.0, 1.0, 1.0),
        geometry_kind="top_group",
        confidence=1.0,
        fill_ratio=1.0,
        frame=frame,
        session=S456_QUERY.review_id,
    )
    normalized = normalize_public_meld_crop(image, candidate)
    width, height = normalized.image.size
    b1 = int(round(width / 3.0)) + d1
    b2 = int(round(2.0 * width / 3.0)) + d2
    if not (0 < b1 < b2 < width):
        return []
    return [
        _square_tile_canvas(normalized.image.crop((0, 0, b1, height))),
        _square_tile_canvas(normalized.image.crop((b1, 0, b2, height))),
        _square_tile_canvas(normalized.image.crop((b2, 0, width, height))),
    ]


def run(repository_root: str | Path = ".", radius: int = 6) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    strip = root / S456_QUERY.strip_path
    frames = _load_query_frames(strip, 5, S456_QUERY)
    profile = load_opponent_meld_domain_profile(
        root / "references/vision/2026-10-01/opponent_meld_domain_profile_v0_1.json"
    )
    tile_ids, synthetic_images, bank = _synthetic_opponent_domain_bank(
        root / "dataset/tiles_runtime_v0_2",
        root / "references/vision/2026-10-01/concealed_template_match_lineage.development.json",
        profile,
        S456_QUERY.query_match_group,
    )
    model, transform, weights = _load_model()
    prototypes = _mean_prototypes(
        tile_ids, _embed_images(synthetic_images, model, transform)
    )

    rows = []
    for d1 in range(-radius, radius + 1):
        for d2 in range(-radius, radius + 1):
            per_frame = []
            valid = True
            for frame, source_frame in zip(frames, S456_QUERY.source_frame_estimates):
                faces = _candidate_faces(frame, source_frame, d1, d2)
                if len(faces) != 3:
                    valid = False
                    break
                embeddings = _embed_images(faces, model, transform)
                per_frame.append([_scores(e, prototypes) for e in embeddings])
            if not valid:
                continue
            mean_rows = _mean_score_rows(per_frame)
            legal = rank_regular_public_meld_identity(mean_rows)
            expected = sorted(S456_QUERY.review_id and ["S4", "S5", "S6"])
            correct = legal.top_tiles is not None and sorted(legal.top_tiles) == expected
            rows.append({
                "boundary_delta_px": [d1, d2],
                "top_tiles": list(legal.top_tiles) if legal.top_tiles else None,
                "top_score": legal.top_score,
                "runner_up_tiles": list(legal.runner_up_tiles) if legal.runner_up_tiles else None,
                "runner_up_score": legal.runner_up_score,
                "margin": legal.margin,
                "correct": correct,
            })

    correct_rows = [r for r in rows if r["correct"]]
    return {
        "schema_version": "opponent_meld_boundary_diagnostic_v0_1",
        "date": "2026-10-01",
        "issue": 69,
        "review_id": S456_QUERY.review_id,
        "purpose": "development_only_split_boundary_sensitivity",
        "radius_px_on_normalized_row": radius,
        "candidate_count": len(rows),
        "correct_candidate_count": len(correct_rows),
        "best_correct_candidates": sorted(
            correct_rows, key=lambda r: (-(r["top_score"] or -1.0), r["boundary_delta_px"])
        )[:10],
        "baseline": next(
            (r for r in rows if r["boundary_delta_px"] == [0, 0]), None
        ),
        "model": {"name": "mobilenet_v3_small_imagenet1k_v1", "weights": weights},
        "synthetic_bank": bank,
        "runtime_identity_threshold_unchanged": RUNTIME_IDENTITY_THRESHOLD,
        "changes_runtime_behavior": False,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--radius", type=int, default=6)
    args = parser.parse_args()
    report = run(radius=args.radius)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["baseline"], sort_keys=True))
    print(f"correct_candidates={report['correct_candidate_count']}/{report['candidate_count']}")


if __name__ == "__main__":
    main()
