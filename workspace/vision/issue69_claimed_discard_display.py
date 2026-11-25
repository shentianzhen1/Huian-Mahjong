"""Fail-closed review of a claimed-discard display for #69.

This is development-only source evidence. It validates measured pip geometry
and colour from a system response-window tile display. It does not infer the
action kind and it is not a river-growth observer.
"""
from __future__ import annotations

from statistics import median
from typing import Any


def _unknown(reason: str) -> dict[str, Any]:
    return {
        "schema_version": "issue69_claimed_discard_display_review_v0_1",
        "status": "UNKNOWN",
        "reason": reason,
        "tile_candidate": None,
        "claimed_discard_display_directly_observed": False,
        "river_growth_directly_observed": False,
        "action_kind_inferred": False,
        "machine_confirmed": False,
        "runtime_eligible": False,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def _is_red(hue: float) -> bool:
    return 0 <= hue <= 20 or 165 <= hue <= 179


def review_claimed_discard_display(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("schema_version") != "issue69_claimed_discard_display_pips_v0_1":
        return _unknown("unsupported_schema")
    if data.get("development_only") is not True:
        return _unknown("not_development_only")

    source = data.get("source", {})
    if (
        source.get("source_session") != "session_c4d1b879367aeca8"
        or source.get("sha256")
        != "c4d1b879367aeca88f2ef950316a5737e5f94d934314ca038c543b041bd2360a"
        or source.get("original_match_group")
        != "reviewed_match_2026_09_26_first_hand"
    ):
        return _unknown("source_scope_mismatch")

    region = data.get("region", {})
    if (
        region.get("semantic_role") != "claimed_discard_display"
        or region.get("privacy_scope") != "tile_face_only"
    ):
        return _unknown("region_semantics_mismatch")

    observations = data.get("observations")
    if not isinstance(observations, list) or len(observations) < 5:
        return _unknown("insufficient_stable_frames")

    valid_frames = 0
    normalized_layouts: list[tuple[float, ...]] = []
    for row in observations:
        circles = row.get("circles")
        if not isinstance(circles, list) or len(circles) != 6:
            return _unknown("circle_count_not_six")
        parsed = []
        for circle in circles:
            if not isinstance(circle, list) or len(circle) != 4:
                return _unknown("invalid_circle_measurement")
            x, y, radius, hue = map(float, circle)
            if not (7 <= radius <= 12 and 0 <= hue <= 179):
                return _unknown("circle_measurement_out_of_range")
            parsed.append((x, y, radius, hue))

        # Cluster by geometry rather than trusting source ordering.
        by_y = sorted(parsed, key=lambda item: (item[1], item[0]))
        rows = [sorted(by_y[i:i + 2], key=lambda item: item[0]) for i in (0, 2, 4)]
        if any(abs(pair[0][1] - pair[1][1]) > 2.0 for pair in rows):
            return _unknown("not_two_columns_by_three_rows")
        left = [pair[0][0] for pair in rows]
        right = [pair[1][0] for pair in rows]
        if max(left) - min(left) > 2.0 or max(right) - min(right) > 2.0:
            return _unknown("column_alignment_unstable")
        if not all(15 <= (r - l) <= 21 for l, r in zip(left, right)):
            return _unknown("column_spacing_invalid")

        row_y = [sum(item[1] for item in pair) / 2 for pair in rows]
        if not (row_y[1] - row_y[0] >= 14 and row_y[2] - row_y[1] >= 12):
            return _unknown("row_spacing_invalid")

        top_hues = [item[3] for item in rows[0]]
        lower_hues = [item[3] for pair in rows[1:] for item in pair]
        if not all(55 <= hue <= 85 for hue in top_hues):
            return _unknown("top_pair_not_green")
        if not all(_is_red(hue) for hue in lower_hues):
            return _unknown("lower_four_not_red")

        normalized_layouts.append(tuple(
            round(value, 2)
            for pair in rows
            for item in pair
            for value in item[:3]
        ))
        valid_frames += 1

    if valid_frames < 5:
        return _unknown("insufficient_valid_frames")

    # The source display is static enough that the median centres must remain
    # nearly fixed. This guards against six unrelated circles entering the ROI.
    columns_left = []
    columns_right = []
    for row in observations:
        parsed = sorted(
            [tuple(map(float, circle)) for circle in row["circles"]],
            key=lambda item: (item[1], item[0]),
        )
        pairs = [sorted(parsed[i:i + 2], key=lambda item: item[0]) for i in (0, 2, 4)]
        columns_left.extend(pair[0][0] for pair in pairs)
        columns_right.extend(pair[1][0] for pair in pairs)
    if (
        max(abs(x - median(columns_left)) for x in columns_left) > 2.0
        or max(abs(x - median(columns_right)) for x in columns_right) > 2.0
    ):
        return _unknown("cross_frame_layout_unstable")

    boundary = data.get("semantic_boundary", {})
    if (
        boundary.get("claimed_discard_display_directly_observed") is not True
        or boundary.get("river_growth_directly_observed") is not False
        or boundary.get("action_kind_inferred_from_this_region") is not False
        or boundary.get("runtime_identity_ready") is not False
        or boundary.get("formal_promotion_evidence") is not False
        or boundary.get("safe_for_runtime") is not False
        or boundary.get("safe_for_executor") is not False
    ):
        return _unknown("semantic_boundary_changed")

    return {
        "schema_version": "issue69_claimed_discard_display_review_v0_1",
        "status": "DIRECT_DISPLAY_P6_DEVELOPMENT",
        "reason": "six_stable_circle_pips_with_p6_colour_layout",
        "tile_candidate": "P6",
        "valid_frame_votes": valid_frames,
        "source_sha256": source["sha256"],
        "original_match_group": source["original_match_group"],
        "claimed_discard_display_directly_observed": True,
        "river_growth_directly_observed": False,
        "action_kind_inferred": False,
        "machine_confirmed": False,
        "runtime_eligible": False,
        "development_only": True,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }
