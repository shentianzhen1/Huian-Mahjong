"""Fail-closed event-order review for #69 pass/draw/discard windows.

The window establishes source-scoped temporal facts only. UI disappearance does
not prove PASS, and a draw/discard component does not prove tile identity.
"""
from __future__ import annotations

from typing import Any


EXPECTED_SHA = "fba5f67d244fb5bdc916f24707de288fef939a9444fa66bec21347e52bd64fc3"
EXPECTED_GROUP = "reviewed_match_2026_09_26_first_hand"
EXPECTED_STATES = (
    "RESPONSE_UI_VISIBLE",
    "RESPONSE_UI_CLEARED",
    "RIGHT_DRAW_COMPONENT_VISIBLE",
    "DRAW_TILE_ENTERING_DISCARD_TRANSITION",
    "TOP_DISCARD_DISPLAY_VISIBLE",
)


def _unknown(reason: str) -> dict[str, Any]:
    return {
        "schema_version": "issue69_pass_draw_discard_review_v0_1",
        "status": "UNKNOWN",
        "reason": reason,
        "response_resolution_observed": False,
        "pass_action_machine_confirmed": False,
        "draw_event_observed": False,
        "discard_event_observed": False,
        "draw_tile_identity": None,
        "discard_tile_identity": None,
        "same_draw_then_discard_identity_machine_confirmed": False,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def review_pass_draw_discard_window(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("schema_version") != "issue69_hand1_pass_draw_discard_window_v0_1":
        return _unknown("unsupported_schema")
    if data.get("development_only") is not True:
        return _unknown("not_development_only")
    source = data.get("source", {})
    if (
        source.get("role") != "exact_full_source_recording"
        or source.get("sha256") != EXPECTED_SHA
        or source.get("original_match_group") != EXPECTED_GROUP
    ):
        return _unknown("source_scope_mismatch")

    window = data.get("event_window", {})
    keys = (
        "response_visible",
        "response_cleared",
        "draw_region_visible",
        "discard_transition",
        "discard_display_stable",
    )
    rows = []
    for key, expected_state in zip(keys, EXPECTED_STATES):
        row = window.get(key)
        if not isinstance(row, dict) or row.get("state") != expected_state:
            return _unknown("event_state_missing_or_changed")
        frame = row.get("frame")
        second = row.get("source_time_seconds")
        if type(frame) is not int or frame < 0:
            return _unknown("invalid_frame")
        if not isinstance(second, (int, float)) or isinstance(second, bool) or second < 0:
            return _unknown("invalid_timestamp")
        rows.append((frame, float(second)))

    if any(rows[i][0] >= rows[i + 1][0] for i in range(len(rows) - 1)):
        return _unknown("frame_order_invalid")
    if any(rows[i][1] >= rows[i + 1][1] for i in range(len(rows) - 1)):
        return _unknown("timestamp_order_invalid")

    safe = data.get("machine_interpretation", {})
    if (
        safe.get("response_resolution_observed") is not True
        or safe.get("response_choice_identity") != "UNKNOWN"
        or safe.get("pass_action_machine_confirmed") is not False
        or safe.get("draw_event_observed") is not True
        or safe.get("draw_tile_identity") != "UNKNOWN"
        or safe.get("discard_event_observed") is not True
        or safe.get("discard_tile_identity") != "UNKNOWN"
        or safe.get("same_draw_then_discard_identity_machine_confirmed") is not False
    ):
        return _unknown("machine_semantic_boundary_changed")

    return {
        "schema_version": "issue69_pass_draw_discard_review_v0_1",
        "status": "SOURCE_LOCKED_EVENT_ORDER",
        "reason": "response_clears_before_draw_component_then_discard_transition",
        "source_sha256": source["sha256"],
        "original_match_group": source["original_match_group"],
        "frames": {key: window[key]["frame"] for key in keys},
        "response_resolution_observed": True,
        "pass_action_machine_confirmed": False,
        "draw_event_observed": True,
        "discard_event_observed": True,
        "draw_tile_identity": None,
        "discard_tile_identity": None,
        "same_draw_then_discard_identity_machine_confirmed": False,
        "development_only": True,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }
