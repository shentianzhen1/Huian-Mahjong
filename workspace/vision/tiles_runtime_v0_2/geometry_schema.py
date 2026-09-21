"""Vision geometry schema and read-only compatibility for legacy annotations."""
from __future__ import annotations

from copy import deepcopy
from typing import Any


REGIONS = frozenset({"hand", "draw_visual", "meld", "gold", "unknown"})
LEGACY_REGION_ALIASES = {"draw": "draw_visual"}


def canonical_region(region: str) -> str:
    """Return the current visual-region name without mutating stored truth."""
    return LEGACY_REGION_ALIASES.get(region, region)


def canonical_components(components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = deepcopy(components)
    for component in result:
        component["region_candidate"] = canonical_region(component["region_candidate"])
    return result


def geometry_counts(components: list[dict[str, Any]]) -> dict[str, int]:
    regions = [canonical_region(component["region_candidate"]) for component in components]
    hand = regions.count("hand")
    draw_visual = regions.count("draw_visual")
    return {
        "expected_hand_region_count": hand,
        "expected_draw_visual_count": draw_visual,
        "expected_concealed_tile_count": hand + draw_visual,
    }


def compatibility_view(row: dict[str, Any]) -> dict[str, Any]:
    """Expose a current-schema view while leaving a frozen source row untouched."""
    view = deepcopy(row)
    components = canonical_components(row.get("components", []))
    derived = geometry_counts(components)
    view["components"] = components
    view["frame_state"] = row.get("frame_state", row.get("trust_state", "trusted"))
    view["animation_type"] = row.get("animation_type")
    view["scene_type"] = row.get("scene_type")
    view["expected_hand_region_count"] = row.get(
        "expected_hand_region_count",
        row.get("expected_hand_component_count", derived["expected_hand_region_count"]),
    )
    view["expected_draw_visual_count"] = row.get(
        "expected_draw_visual_count", derived["expected_draw_visual_count"]
    )
    view["expected_concealed_tile_count"] = row.get(
        "expected_concealed_tile_count",
        view["expected_hand_region_count"] + view["expected_draw_visual_count"],
    )
    warnings: list[str] = []
    if view["expected_draw_visual_count"] not in (0, 1):
        warnings.append("draw_visual_count_outside_normal_0_or_1")
    if view["expected_concealed_tile_count"] != (
        view["expected_hand_region_count"] + view["expected_draw_visual_count"]
    ):
        warnings.append("concealed_count_invariant_mismatch")
    if view["expected_hand_region_count"] != derived["expected_hand_region_count"]:
        warnings.append("hand_region_count_component_mismatch")
    if view["expected_draw_visual_count"] != derived["expected_draw_visual_count"]:
        warnings.append("draw_visual_count_component_mismatch")
    view["schema_warnings"] = warnings
    return view


def new_geometry_row_fields(
    components: list[dict[str, Any]],
    frame_state: str,
    animation_type: str | None = None,
    scene_type: str | None = None,
) -> dict[str, Any]:
    """Build fields for new annotations; counts always derive from visible geometry."""
    canonical = canonical_components(components)
    counts = geometry_counts(canonical)
    return {
        "frame_state": frame_state,
        "animation_type": animation_type if frame_state == "animation" else None,
        "scene_type": scene_type if frame_state == "non_game" else None,
        "components": canonical,
        "hand_bboxes": [c["pixel_bbox"] for c in canonical if c["region_candidate"] == "hand"],
        "meld_bboxes": [c["pixel_bbox"] for c in canonical if c["region_candidate"] == "meld"],
        "draw_visual_bboxes": [
            c["pixel_bbox"] for c in canonical if c["region_candidate"] == "draw_visual"
        ],
        "gold_bbox": next(
            (c["pixel_bbox"] for c in canonical if c["region_candidate"] == "gold"), None
        ),
        **counts,
    }
