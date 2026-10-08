"""Fail-closed integrity audit for the Issue #69 Hand-1 replay fixture."""
from __future__ import annotations

from typing import Any

EXPECTED_GROUP = "reviewed_match_2026_09_26_first_hand"
YOUJIN_CHAIN = [
    "PLAYER_DISCARD_P5_ENTER_YOUJIN",
    "OPPONENT_RESPONSE_DRAW",
    "OPPONENT_MANDATORY_DISCARD_M3",
    "PLAYER_CONTINUATION_DRAW_P4",
    "PLAYER_DECLARE_YOUJIN",
    "SETTLEMENT_PLUS_68",
]


def audit_hand1_timeline(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    events = data.get("events", [])
    orders = [row.get("order") for row in events]
    if orders != list(range(1, len(events) + 1)):
        errors.append("EVENT_ORDER_NOT_CONTIGUOUS")

    groups = {row.get("original_match_group") for row in events}
    if groups != {EXPECTED_GROUP}:
        errors.append("MATCH_GROUP_SCOPE_MISMATCH")

    if data.get("machine_closed_event_count") != sum(
        bool(row.get("machine_confirmed")) for row in events
    ):
        errors.append("MACHINE_CLOSED_COUNT_MISMATCH")

    if data.get("development_candidate_event_count") != len(events):
        errors.append("DEVELOPMENT_EVENT_COUNT_MISMATCH")

    claim_events = [
        row for row in events
        if row.get("kind") in {"CROSS_ACTOR_CLAIM_SEQUENCE", "CHAIN_TO_SECOND_OPPONENT_MELD"}
    ]
    if len(claim_events) != 2:
        errors.append("EXPECTED_TWO_CLAIM_EVENTS")
    for row in claim_events:
        truth = row.get("human_reviewed_truth", {})
        if row.get("kind") == "CROSS_ACTOR_CLAIM_SEQUENCE":
            claimed = truth.get("player_discard")
            meld = truth.get("opponent_meld", [])
        else:
            claimed = truth.get("player_next_discard")
            meld = truth.get("opponent_meld", [])
        if claimed not in meld:
            errors.append("CLAIMED_DISCARD_NOT_CONSUMED_BY_MELD")

    youjin = next((row for row in events if row.get("kind") == "YOUJIN_TERMINAL_STATE_CHAIN"), None)
    if youjin is None:
        errors.append("YOUJIN_TERMINAL_CHAIN_MISSING")
    else:
        if youjin.get("reviewed_rule_chain") != YOUJIN_CHAIN:
            errors.append("YOUJIN_RESPONSE_CHAIN_INVALID")
        settlement = youjin.get("settlement", {})
        subtotal = (
            settlement.get("base", 0)
            + settlement.get("gold_fan", 0)
            + settlement.get("flower_fan", 0)
            + settlement.get("kong_fan", 0)
        )
        if subtotal * settlement.get("multiplier", 0) != settlement.get("net_score"):
            errors.append("YOUJIN_SETTLEMENT_ARITHMETIC_MISMATCH")

    if any(row.get("machine_confirmed") for row in events):
        errors.append("UNEXPECTED_MACHINE_PROMOTION")
    if any(data.get(k) for k in ("formal_promotion_evidence", "safe_for_runtime", "safe_for_hint", "safe_for_executor")):
        errors.append("SAFETY_BOUNDARY_BROKEN")

    return {
        "schema_version": "issue69_hand1_replay_audit_v0_1",
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "event_count": len(events),
        "claim_event_count": len(claim_events),
        "youjin_terminal_present": youjin is not None,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }
