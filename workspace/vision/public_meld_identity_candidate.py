"""Frozen development candidate contract for public-meld identity.

This records the candidate selected on the reviewed P6/S4 development queries.
Changing feature family or inset ratio creates a new candidate and must not be
presented as validation of the frozen candidate.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "public_meld_identity_candidate_v0_1"
FROZEN_CANDIDATE_ID = "legacy_gray_center_inset_0_12"
FROZEN_FEATURE_FAMILY = "legacy_public_gray"
FROZEN_INSET_RATIO = 0.12
FROZEN_SELECTION_QUERY_IDS = (
    "first_hand_174s_p6",
    "first_hand_174s_s4",
)
FROZEN_SELECTION_MATCH_GROUP = "reviewed_match_2026_09_26_first_hand"


@dataclass(frozen=True)
class PublicMeldIdentityCandidate:
    candidate_id: str
    status: str
    frozen_on: str
    feature_family: str
    inset_ratio: float
    normalization_scope: str
    template_bank_preprocessing_allowed: bool
    selection_query_ids: tuple[str, ...]
    selection_match_group: str
    selected_on_selection_queries: bool
    future_holdout_must_be_source_disjoint: bool
    future_holdout_must_not_change_candidate: bool
    future_holdout_query_pixels_template_eligible: bool
    identity_threshold_lowering_allowed: bool
    minimum_independent_holdout_match_groups: int
    wire_into_runtime: bool
    safe_for_hint: bool
    safe_for_executor: bool
    formal_promotion_evidence: bool


def load_public_meld_identity_candidate(
    path: str | Path,
) -> PublicMeldIdentityCandidate:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported public meld identity candidate schema")

    normalization = payload.get("normalization")
    selection = payload.get("selection_evidence")
    validation = payload.get("validation_policy")
    runtime = payload.get("runtime_policy")
    if not all(isinstance(item, dict) for item in (
        normalization, selection, validation, runtime
    )):
        raise ValueError("candidate contract sections are required")

    candidate = PublicMeldIdentityCandidate(
        candidate_id=str(payload.get("candidate_id", "")),
        status=str(payload.get("status", "")),
        frozen_on=str(payload.get("frozen_on", "")),
        feature_family=str(payload.get("feature_family", "")),
        inset_ratio=float(normalization.get("inset_ratio")),
        normalization_scope=str(normalization.get("scope", "")),
        template_bank_preprocessing_allowed=bool(
            normalization.get("template_bank_preprocessing_allowed")
        ),
        selection_query_ids=tuple(str(x) for x in selection.get("query_ids", ())),
        selection_match_group=str(selection.get("query_match_group", "")),
        selected_on_selection_queries=bool(selection.get("selected_on_these_queries")),
        future_holdout_must_be_source_disjoint=bool(
            validation.get("future_holdout_must_be_source_disjoint")
        ),
        future_holdout_must_not_change_candidate=bool(
            validation.get("future_holdout_must_not_change_candidate")
        ),
        future_holdout_query_pixels_template_eligible=bool(
            validation.get("future_holdout_query_pixels_template_eligible")
        ),
        identity_threshold_lowering_allowed=bool(
            validation.get("identity_threshold_lowering_allowed")
        ),
        minimum_independent_holdout_match_groups=int(
            validation.get("minimum_independent_holdout_match_groups", 0)
        ),
        wire_into_runtime=bool(runtime.get("wire_into_runtime")),
        safe_for_hint=bool(runtime.get("safe_for_hint")),
        safe_for_executor=bool(runtime.get("safe_for_executor")),
        formal_promotion_evidence=bool(runtime.get("formal_promotion_evidence")),
    )
    validate_frozen_public_meld_identity_candidate(candidate)
    return candidate


def validate_frozen_public_meld_identity_candidate(
    candidate: PublicMeldIdentityCandidate,
) -> None:
    expected: dict[str, Any] = {
        "candidate_id": FROZEN_CANDIDATE_ID,
        "status": "frozen_development_candidate",
        "feature_family": FROZEN_FEATURE_FAMILY,
        "inset_ratio": FROZEN_INSET_RATIO,
        "normalization_scope": "query_side_split_face_only",
        "template_bank_preprocessing_allowed": False,
        "selection_query_ids": FROZEN_SELECTION_QUERY_IDS,
        "selection_match_group": FROZEN_SELECTION_MATCH_GROUP,
        "selected_on_selection_queries": True,
        "future_holdout_must_be_source_disjoint": True,
        "future_holdout_must_not_change_candidate": True,
        "future_holdout_query_pixels_template_eligible": False,
        "identity_threshold_lowering_allowed": False,
        "minimum_independent_holdout_match_groups": 1,
        "wire_into_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
        "formal_promotion_evidence": False,
    }
    for field, value in expected.items():
        if getattr(candidate, field) != value:
            raise ValueError(f"frozen candidate contract changed: {field}")
    if not candidate.frozen_on:
        raise ValueError("frozen_on is required")


def assert_holdout_is_eligible_for_frozen_candidate(
    candidate: PublicMeldIdentityCandidate,
    *,
    holdout_match_group: str,
    candidate_changed_after_freeze: bool,
    query_pixels_used_as_templates: bool,
) -> None:
    """Fail closed before a future holdout is scored."""
    validate_frozen_public_meld_identity_candidate(candidate)
    if not holdout_match_group:
        raise ValueError("holdout_match_group is required")
    if holdout_match_group == candidate.selection_match_group:
        raise ValueError("holdout must use an independent original match group")
    if candidate_changed_after_freeze:
        raise ValueError("candidate changed after freeze")
    if query_pixels_used_as_templates:
        raise ValueError("holdout query pixels cannot be identity templates")
