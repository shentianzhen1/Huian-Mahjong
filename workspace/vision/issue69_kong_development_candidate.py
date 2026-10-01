"""Compose #69 machine evidence into a development-only kong candidate.

This module intentionally does NOT promote public-meld SIFT into Runtime
identity. It combines already-recorded, source-scoped development evidence so
the offline replay can distinguish "machine-supported candidate" from human
truth and from runtime-corroborated actions.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_HAND = "references/vision/2026-10-01/issue69_hand1_p6_ming_gang_hand_count_v0_1.json"
_STRUCTURE = "references/vision/2026-10-01/issue69_hand1_p6_ming_gang_structure_v0_1.json"
_IDENTITY = "references/vision/2026-10-01/issue69_hand1_p6_public_meld_sift_result_v0_1.json"


def _unknown(reason: str, *, source_sha256: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": "issue69_kong_development_candidate_v0_1",
        "status": "UNKNOWN",
        "reason": reason,
        "action_candidate": None,
        "tile_candidate": None,
        "source_sha256": source_sha256,
        "claimed_discard_directly_observed": False,
        "machine_confirmed": False,
        "runtime_eligible": False,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def build_kong_development_candidate(
    hand_count: dict[str, Any],
    structure: dict[str, Any],
    identity: dict[str, Any],
) -> dict[str, Any]:
    """Return a fail-closed development candidate from three evidence layers."""
    for name, payload in (
        ("hand_count", hand_count),
        ("structure", structure),
        ("identity", identity),
    ):
        if payload.get("development_only") is not True:
            return _unknown(f"{name}_not_development_only")

    hand_source = hand_count.get("source", {})
    identity_source = identity.get("source", {})
    source_sha = structure.get("source_sha256")
    if not source_sha or not (
        hand_source.get("sha256") == source_sha == identity_source.get("sha256")
    ):
        return _unknown("source_sha_mismatch", source_sha256=source_sha)

    match_group = structure.get("original_match_group")
    if not match_group or not (
        hand_source.get("original_match_group")
        == match_group
        == identity_source.get("match_group")
    ):
        return _unknown("original_match_group_mismatch", source_sha256=source_sha)

    count = hand_count.get("claim_count_review", {})
    if (
        count.get("before_count") != 16
        or count.get("after_count") != 13
        or count.get("removed_count") != 3
        or count.get("new_meld_face_count") != 4
        or count.get("pre_sample_brackets_onset") is not True
        or count.get("draw_event_in_samples") is not False
        or count.get("discard_event_in_samples") is not False
    ):
        return _unknown("hand_count_gate_not_satisfied", source_sha256=source_sha)

    geometry = structure.get("public_meld_geometry", {})
    stack_states = tuple(geometry.get("stack_states", ()))
    if (
        structure.get("structural_state")
        != "NEW_STACKED_FOUR_FACE_MELD_WITH_THREE_CONCEALED_TILES_CONSUMED"
        or len(stack_states) < 3
        or any(state != "STACKED" for state in stack_states)
        or geometry.get("onset_frame") != count.get("new_meld_first_visible_frame")
    ):
        return _unknown("stacked_four_face_structure_not_stable", source_sha256=source_sha)

    if (
        structure.get("replacement_draw", {}).get("first_visible_component_frame", -1)
        <= count.get("after_frame", -1)
    ):
        return _unknown("replacement_draw_contaminates_claim_window", source_sha256=source_sha)

    ranking = identity.get("ranking", {})
    boundary = identity.get("evidence_boundary", {})
    tile = ranking.get("top1_tile")
    if (
        not isinstance(tile, str)
        or not tile
        or ranking.get("source_disjoint_ranking") is not True
        or ranking.get("winner_other_match_groups", 0) < 2
        or ranking.get("minimum_other_match_groups", 0) < 2
    ):
        return _unknown("public_meld_identity_not_source_disjoint", source_sha256=source_sha)

    # This is deliberately not a production acceptance rule. The frozen SIFT
    # path has no production threshold and this match was already inspected
    # during candidate selection. Preserve that boundary in the output.
    if (
        boundary.get("production_acceptance_threshold") is not None
        or boundary.get("blind_validation") is not False
        or boundary.get("formal_promotion_evidence") is not False
        or boundary.get("safe_for_runtime") is not False
        or boundary.get("safe_for_executor") is not False
    ):
        return _unknown("identity_evidence_boundary_changed", source_sha256=source_sha)

    return {
        "schema_version": "issue69_kong_development_candidate_v0_1",
        "status": "DEVELOPMENT_MING_GANG_CANDIDATE",
        "reason": "stacked_four_face_meld_plus_hand_minus_three_plus_source_disjoint_top1",
        "action_candidate": "MING_GANG",
        "tile_candidate": tile,
        "actor": "player",
        "source_sha256": source_sha,
        "original_match_group": match_group,
        "structure_evidence": {
            "stacked_votes": len(stack_states),
            "hand_before": count["before_count"],
            "hand_after": count["after_count"],
            "removed_count": count["removed_count"],
            "meld_face_count": count["new_meld_face_count"],
            "meld_onset_frame": geometry["onset_frame"],
            "replacement_draw_first_frame": structure["replacement_draw"][
                "first_visible_component_frame"
            ],
        },
        "identity_evidence": {
            "backend": ranking.get("backend"),
            "top1_tile": tile,
            "top1_score": ranking.get("top1_score"),
            "runner_up_tile": ranking.get("runner_up_tile"),
            "runner_up_score": ranking.get("runner_up_score"),
            "margin": ranking.get("margin"),
            "winner_other_match_groups": ranking.get("winner_other_match_groups"),
            "source_disjoint_ranking": True,
            "production_acceptance_threshold": None,
        },
        "claimed_discard_directly_observed": False,
        "machine_confirmed": False,
        "runtime_eligible": False,
        "development_only": True,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def build_hand1_candidate_from_repository(repository_root: str | Path = ".") -> dict[str, Any]:
    root = Path(repository_root)
    hand = json.loads((root / _HAND).read_text(encoding="utf-8"))
    structure = json.loads((root / _STRUCTURE).read_text(encoding="utf-8"))
    identity = json.loads((root / _IDENTITY).read_text(encoding="utf-8"))
    return build_kong_development_candidate(hand, structure, identity)
