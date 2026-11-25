"""Issue #69 development-only public meld structure regression matrix.

The matrix combines already-reviewed structure reports across independent real
match events. It validates geometry/state-transition coverage only. Tile
identity and Mahjong action semantics remain outside this contract.

Inputs:
- hand1 public STACKED four-face structure evidence committed in the repo;
- round6 private FLAT3 -> STACKED4 replay output;
- round8 private new-FLAT3 replay output for both actors.

Private reports stay local. The returned summary is safe to inspect but is not
formal Runtime promotion evidence and never enables Hint or Executor.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "issue69_meld_structure_regression_matrix_v0_1"
HAND1_STRUCTURE = (
    "references/vision/2026-10-01/"
    "issue69_hand1_p6_ming_gang_structure_v0_1.json"
)


def _fail(reason: str) -> ValueError:
    return ValueError(f"meld structure regression contract failed: {reason}")


def _stable_round8_rows(report: dict[str, Any], actor: str) -> list[dict[str, Any]]:
    return [
        row for row in report.get("trace", ())
        if row.get("actor") == actor and row.get("baseline_window") is False
    ]


def _round8_event(report: dict[str, Any], actor: str) -> dict[str, Any]:
    rows = [
        row for row in report.get("machine_events", ())
        if row.get("actor") == actor
    ]
    if len(rows) != 1:
        raise _fail(f"round8_{actor}_event_count_changed")
    return rows[0]


def build_meld_structure_regression_matrix(
    hand1_structure: dict[str, Any],
    round6_report: dict[str, Any],
    round8_report: dict[str, Any],
) -> dict[str, Any]:
    """Validate the four currently reviewed real-event structure cases."""
    if hand1_structure.get("development_only") is not True:
        raise _fail("hand1_not_development_only")
    if hand1_structure.get("structural_state") != (
        "NEW_STACKED_FOUR_FACE_MELD_WITH_THREE_CONCEALED_TILES_CONSUMED"
    ):
        raise _fail("hand1_structural_state_changed")
    hand1_geometry = hand1_structure.get("public_meld_geometry", {})
    hand1_states = tuple(hand1_geometry.get("stack_states", ()))
    if len(hand1_states) < 5 or any(
        state != "STACKED" for state in hand1_states
    ):
        raise _fail("hand1_stacked_votes_not_stable")
    if hand1_structure.get("tile_identity") != "UNKNOWN":
        raise _fail("hand1_structure_claims_tile_identity")
    if any(hand1_structure.get(flag) is not False for flag in (
        "formal_promotion_evidence",
        "safe_for_runtime",
        "safe_for_hint",
        "safe_for_executor",
    )):
        raise _fail("hand1_safety_boundary_changed")

    if round6_report.get("result") != "PASS":
        raise _fail("round6_private_replay_not_pass")
    round6_obs = round6_report.get("emitted_observation", {})
    if (
        round6_obs.get("kind") != "MELD_DELTA"
        or round6_obs.get("previous_group_size") != 3
        or round6_obs.get("group_size") != 4
        or round6_obs.get("tile_identity_complete") is not False
    ):
        raise _fail("round6_three_to_four_contract_changed")
    upgrades = round6_report.get("meld_upgrade_candidates", ())
    if len(upgrades) != 1:
        raise _fail("round6_upgrade_candidate_count_changed")
    upgrade = upgrades[0]
    if (
        upgrade.get("previous_group_size") != 3
        or upgrade.get("current_group_size") != 4
        or upgrade.get("tile_identity_complete") is not False
        or upgrade.get("action_kind") != "UNKNOWN"
        or upgrade.get("safe_for_runtime") is not False
        or upgrade.get("safe_for_executor") is not False
    ):
        raise _fail("round6_upgrade_safety_boundary_changed")
    round6_stacked_votes = sum(
        1 for row in round6_report.get("trace", ())
        if row.get("stack_state") == "STACKED"
    )
    if round6_stacked_votes < 5:
        raise _fail("round6_stacked_votes_not_stable")

    if round8_report.get("result") != "PASS":
        raise _fail("round8_private_replay_not_pass")
    if round8_report.get(
        "human_action_semantics_used_for_machine_result"
    ) is not False:
        raise _fail("round8_machine_result_uses_human_action_semantics")
    if round8_report.get("tile_identity_policy") != "UNKNOWN":
        raise _fail("round8_identity_policy_changed")
    if any(round8_report.get(flag) is not False for flag in (
        "formal_promotion_evidence",
        "safe_for_runtime",
        "safe_for_hint",
        "safe_for_executor",
    )):
        raise _fail("round8_safety_boundary_changed")

    player_rows = _stable_round8_rows(round8_report, "player")
    opponent_rows = _stable_round8_rows(round8_report, "opponent")
    if len(player_rows) < 5 or not all(
        row.get("observer_trusted") is True
        and row.get("group_count") == 1
        and row.get("structural_face_counts") == [3]
        and row.get("stack_states") == ["FLAT"]
        for row in player_rows
    ):
        raise _fail("round8_player_flat3_stable_window_changed")
    if len(opponent_rows) < 5 or not all(
        row.get("observer_trusted") is True
        and row.get("group_count") == 2
        and row.get("structural_face_counts") == [3, 3]
        and row.get("stack_states") == ["FLAT", "FLAT"]
        for row in opponent_rows
    ):
        raise _fail("round8_opponent_multigroup_flat_window_changed")

    player_event = _round8_event(round8_report, "player")
    opponent_event = _round8_event(round8_report, "opponent")
    for actor, event in (
        ("player", player_event),
        ("opponent", opponent_event),
    ):
        if (
            event.get("kind") != "MELD_DELTA"
            or event.get("group_size") != 3
            or event.get("previous_group_size") is not None
            or event.get("tile_identity_complete") is not False
        ):
            raise _fail(f"round8_{actor}_new_flat3_contract_changed")

    events = [
        {
            "event_id": "hand1_new_stacked4",
            "structure_kind": "NEW_STACKED_FOUR_FACE_MELD",
            "stable_vote_count": len(hand1_states),
            "previous_group_size": None,
            "current_group_size": 4,
            "tile_identity": "UNKNOWN",
            "action_kind": "UNKNOWN_FROM_STRUCTURE_LAYER",
        },
        {
            "event_id": "round6_same_group_3_to_4",
            "structure_kind": "SAME_GROUP_FLAT3_TO_STACKED4",
            "stable_vote_count": round6_stacked_votes,
            "previous_group_size": 3,
            "current_group_size": 4,
            "tile_identity": "UNKNOWN",
            "action_kind": "UNKNOWN",
        },
        {
            "event_id": "round8_player_new_flat3",
            "structure_kind": "NEW_FLAT_THREE_FACE_MELD",
            "stable_vote_count": len(player_rows),
            "previous_group_size": None,
            "current_group_size": 3,
            "tile_identity": "UNKNOWN",
            "action_kind": "UNKNOWN",
        },
        {
            "event_id": "round8_opponent_second_flat3",
            "structure_kind": "NEW_FLAT_THREE_FACE_MELD_WITH_PREEXISTING_GROUP",
            "stable_vote_count": len(opponent_rows),
            "previous_group_size": None,
            "current_group_size": 3,
            "tile_identity": "UNKNOWN",
            "action_kind": "UNKNOWN",
        },
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "issue": 69,
        "development_only": True,
        "status": "PASS",
        "event_count": len(events),
        "covered_structure_cases": [
            row["structure_kind"] for row in events
        ],
        "events": events,
        "identity_policy": (
            "UNKNOWN unless independently validated outside structure layer"
        ),
        "action_policy": (
            "structure evidence never promotes Mahjong action semantics by itself"
        ),
        "animation_policy": (
            "accept only frozen stable windows; transient action animation is excluded"
        ),
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def build_from_repository_and_private_reports(
    repository_root: str | Path,
    *,
    round6_report_path: str | Path,
    round8_report_path: str | Path,
) -> dict[str, Any]:
    root = Path(repository_root)
    hand1 = json.loads(
        (root / HAND1_STRUCTURE).read_text(encoding="utf-8")
    )
    round6 = json.loads(
        Path(round6_report_path).read_text(encoding="utf-8")
    )
    round8 = json.loads(
        Path(round8_report_path).read_text(encoding="utf-8")
    )
    return build_meld_structure_regression_matrix(
        hand1, round6, round8
    )
