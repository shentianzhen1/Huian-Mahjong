"""Fail-closed evidence boundary for the #69 first-hand TING prompt."""
from __future__ import annotations

from typing import Any

EXPECTED_SHA = "fba5f67d244fb5bdc916f24707de288fef939a9444fa66bec21347e52bd64fc3"


def review_ting_prompt_slot(data: dict[str, Any]) -> dict[str, Any]:
    base = {
        "schema_version": "issue69_ting_prompt_review_v0_1",
        "status": "UNKNOWN",
        "ting_prompt_observed": False,
        "structural_tenpai_inferred_from_prompt": False,
        "rules_engine_tenpai_confirmed": False,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }
    if data.get("schema_version") != "issue69_hand1_ting_prompt_pending_v0_1":
        return {**base, "reason": "unsupported_schema"}
    source = data.get("source", {})
    if source.get("expected_sha256") != EXPECTED_SHA:
        return {**base, "reason": "source_scope_mismatch"}
    machine = data.get("machine_interpretation", {})
    if (
        data.get("status") != "PENDING_EXACT_SOURCE_UI_REVIEW"
        or machine.get("ting_prompt_observed") is not False
        or machine.get("structural_tenpai_inferred_from_prompt") is not False
        or machine.get("rules_engine_tenpai_confirmed") is not False
    ):
        return {**base, "reason": "pending_boundary_changed"}
    truth = data.get("human_reviewed_truth", {})
    if truth.get("used_for_runtime_promotion") is not False:
        return {**base, "reason": "human_truth_promotion_forbidden"}
    return {
        **base,
        "status": "PENDING_EXACT_SOURCE_UI_REVIEW",
        "reason": "human_reviewed_ting_prompt_requires_independent_ui_observation",
    }
