"""Fail-closed validation gate for public-meld identity promotion evidence.

This module deliberately does NOT promote any classifier or normalization into
Runtime. It only checks whether an experiment is even eligible to be discussed
as source-disjoint validation evidence.

The current 12% inset candidate must fail this gate because it was selected
after inspecting the same P6/S4 development queries.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PublicMeldIdentityValidationEvidence:
    candidate_name: str
    candidate_frozen_before_holdout: bool
    selected_on_evaluated_queries: bool
    source_disjoint_holdout: bool
    holdout_independent_match_groups: int
    evaluated_class_count: int
    identity_threshold_lowered: bool
    query_pixels_used_as_templates: bool

    def __post_init__(self) -> None:
        if not self.candidate_name:
            raise ValueError("candidate_name is required")
        for name in (
            "holdout_independent_match_groups",
            "evaluated_class_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")


@dataclass(frozen=True)
class PublicMeldIdentityValidationGateResult:
    eligible_as_validation_evidence: bool
    blockers: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "public_meld_identity_validation_gate_v0_1",
            "eligible_as_validation_evidence": self.eligible_as_validation_evidence,
            "blockers": list(self.blockers),
            "runtime_promotion_decision": "NOT_DECIDED",
            "formal_promotion_evidence": self.eligible_as_validation_evidence,
            "changes_runtime_behavior": False,
            "safe_for_hint": False,
            "safe_for_executor": False,
        }


def assess_public_meld_identity_validation(
    evidence: PublicMeldIdentityValidationEvidence,
) -> PublicMeldIdentityValidationGateResult:
    """Return whether an experiment qualifies as validation evidence at all.

    Passing this gate does not mean the model is good enough for Runtime. It
    only means the experiment is clean enough to be evaluated as holdout
    evidence. Accuracy/coverage thresholds for any future promotion remain a
    separate decision.
    """
    blockers: list[str] = []

    if not evidence.candidate_frozen_before_holdout:
        blockers.append("candidate_not_frozen_before_holdout")
    if evidence.selected_on_evaluated_queries:
        blockers.append("candidate_selected_on_evaluated_queries")
    if not evidence.source_disjoint_holdout:
        blockers.append("holdout_not_source_disjoint")
    if evidence.holdout_independent_match_groups < 1:
        blockers.append("no_independent_holdout_match_group")
    if evidence.evaluated_class_count < 1:
        blockers.append("no_evaluated_holdout_class")
    if evidence.identity_threshold_lowered:
        blockers.append("identity_threshold_lowered")
    if evidence.query_pixels_used_as_templates:
        blockers.append("query_pixels_used_as_templates")

    return PublicMeldIdentityValidationGateResult(
        eligible_as_validation_evidence=not blockers,
        blockers=tuple(blockers),
    )


def current_inset_candidate_evidence() -> PublicMeldIdentityValidationEvidence:
    """Encode the current 12% inset experiment truth for regression tests/docs."""
    return PublicMeldIdentityValidationEvidence(
        candidate_name="legacy_gray_center_inset_0_12",
        candidate_frozen_before_holdout=False,
        selected_on_evaluated_queries=True,
        source_disjoint_holdout=False,
        holdout_independent_match_groups=0,
        evaluated_class_count=2,
        identity_threshold_lowered=False,
        query_pixels_used_as_templates=False,
    )
