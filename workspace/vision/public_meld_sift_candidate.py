"""Frozen development contract for the public-meld SIFT candidate."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


SCHEMA_VERSION = "public_meld_sift_candidate_v0_1"
CANDIDATE_ID = "public_meld_sift_local_keypoints_v0_1"
FROZEN_SELECTION_MATCH_GROUPS = (
    "reviewed_recording_66fe",
    "reviewed_recording_b389",
    "reviewed_match_2026_09_19_eight_hand",
    "reviewed_recording_14",
    "reviewed_match_2026_09_26_first_hand",
)


@dataclass(frozen=True)
class PublicMeldSiftCandidate:
    candidate_id: str
    status: str
    frozen_on: str
    scale_factor: float
    clahe_clip_limit: float
    clahe_tile_grid: tuple[int, int]
    nfeatures: int
    knn_k: int
    ratio_test: float
    fallback_best_raw_matches: int
    minimum_other_match_groups: int
    selection_match_groups: tuple[str, ...]
    selected_after_reviewing_results: bool
    future_holdout_must_be_new_independent_match_group: bool
    future_holdout_must_not_change_candidate: bool
    future_holdout_query_pixels_template_eligible: bool
    minimum_future_holdout_match_groups: int
    wire_into_runtime: bool
    safe_for_hint: bool
    safe_for_executor: bool
    formal_promotion_evidence: bool


def load_public_meld_sift_candidate(path: str | Path) -> PublicMeldSiftCandidate:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported public meld SIFT candidate schema")

    preprocessing = payload.get("preprocessing")
    detector = payload.get("detector")
    matcher = payload.get("matcher")
    aggregation = payload.get("class_aggregation")
    selection = payload.get("selection_evidence")
    validation = payload.get("validation_policy")
    runtime = payload.get("runtime_policy")
    if not all(isinstance(section, dict) for section in (
        preprocessing, detector, matcher, aggregation, selection, validation, runtime
    )):
        raise ValueError("public meld SIFT candidate sections are required")

    grid = tuple(preprocessing.get("clahe_tile_grid", ()))
    if len(grid) != 2:
        raise ValueError("clahe_tile_grid must contain two values")

    candidate = PublicMeldSiftCandidate(
        candidate_id=str(payload.get("candidate_id", "")),
        status=str(payload.get("status", "")),
        frozen_on=str(payload.get("frozen_on", "")),
        scale_factor=float(preprocessing.get("scale_factor")),
        clahe_clip_limit=float(preprocessing.get("clahe_clip_limit")),
        clahe_tile_grid=(int(grid[0]), int(grid[1])),
        nfeatures=int(detector.get("nfeatures")),
        knn_k=int(matcher.get("knn_k")),
        ratio_test=float(matcher.get("ratio_test")),
        fallback_best_raw_matches=int(matcher.get("fallback_best_raw_matches")),
        minimum_other_match_groups=int(aggregation.get("minimum_other_match_groups")),
        selection_match_groups=tuple(
            str(value) for value in selection.get("selection_match_groups", ())
        ),
        selected_after_reviewing_results=bool(
            selection.get("selected_after_reviewing_these_results")
        ),
        future_holdout_must_be_new_independent_match_group=bool(
            validation.get("future_holdout_must_be_new_independent_match_group")
        ),
        future_holdout_must_not_change_candidate=bool(
            validation.get("future_holdout_must_not_change_candidate")
        ),
        future_holdout_query_pixels_template_eligible=bool(
            validation.get("future_holdout_query_pixels_template_eligible")
        ),
        minimum_future_holdout_match_groups=int(
            validation.get("minimum_future_holdout_match_groups", 0)
        ),
        wire_into_runtime=bool(runtime.get("wire_into_runtime")),
        safe_for_hint=bool(runtime.get("safe_for_hint")),
        safe_for_executor=bool(runtime.get("safe_for_executor")),
        formal_promotion_evidence=bool(runtime.get("formal_promotion_evidence")),
    )
    validate_frozen_public_meld_sift_candidate(candidate)
    return candidate


def validate_frozen_public_meld_sift_candidate(
    candidate: PublicMeldSiftCandidate,
) -> None:
    expected = {
        "candidate_id": CANDIDATE_ID,
        "status": "frozen_development_candidate",
        "scale_factor": 3.0,
        "clahe_clip_limit": 2.0,
        "clahe_tile_grid": (8, 8),
        "nfeatures": 100,
        "knn_k": 2,
        "ratio_test": 0.8,
        "fallback_best_raw_matches": 5,
        "minimum_other_match_groups": 2,
        "selection_match_groups": FROZEN_SELECTION_MATCH_GROUPS,
        "selected_after_reviewing_results": True,
        "future_holdout_must_be_new_independent_match_group": True,
        "future_holdout_must_not_change_candidate": True,
        "future_holdout_query_pixels_template_eligible": False,
        "minimum_future_holdout_match_groups": 1,
        "wire_into_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
        "formal_promotion_evidence": False,
    }
    for field, value in expected.items():
        if getattr(candidate, field) != value:
            raise ValueError(f"frozen SIFT candidate contract changed: {field}")
    if not candidate.frozen_on:
        raise ValueError("frozen_on is required")


def assert_future_sift_holdout_eligible(
    candidate: PublicMeldSiftCandidate,
    *,
    holdout_match_group: str,
    candidate_changed_after_freeze: bool,
    query_pixels_used_as_templates: bool,
) -> None:
    validate_frozen_public_meld_sift_candidate(candidate)
    if not holdout_match_group:
        raise ValueError("holdout_match_group is required")
    if holdout_match_group in candidate.selection_match_groups:
        raise ValueError("SIFT holdout must be a new independent match group")
    if candidate_changed_after_freeze:
        raise ValueError("SIFT candidate changed after freeze")
    if query_pixels_used_as_templates:
        raise ValueError("SIFT holdout query pixels cannot be templates")
