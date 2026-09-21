"""Classify revealed Phase 5C geometry failures without changing the detector.

The JSON report is safe to track: it contains anonymous IDs and geometry only.
Full-frame overlays are local derivatives under ``validation/generated`` and
remain ignored by Git.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from PIL import ImageDraw

from .dynamic_geometry import detect_dynamic_geometry
from .geometry_holdout_metrics import _frame, _match
from .geometry_schema import compatibility_view
from .phase5b_holdout import locate_sources


COLORS = {
    "truth": "#20e070",
    "prediction": "#00a8ff",
    "miss": "#ff304f",
    "region_error": "#ffd60a",
}


def _read_rows(path: Path) -> dict[str, dict]:
    return {
        row["id"]: compatibility_view(row)
        for row in (
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line
        )
    }


def _rightmost_hand_ids(components: list[dict]) -> set[int]:
    indexed = [
        (index, component)
        for index, component in enumerate(components)
        if component["region_candidate"] == "hand"
    ]
    return {
        index
        for index, _ in sorted(indexed, key=lambda item: item[1]["pixel_bbox"][0])[-2:]
    }


def _overlap(first: list[int], second: list[int]) -> bool:
    x, y, width, height = first
    ox, oy, ow, oh = second
    return x < ox + ow and ox < x + width and y < oy + oh and oy < y + height


def _miss_category(index: int, component: dict, all_components: list[dict], rightmost: set[int]) -> str:
    region = component["region_candidate"]
    if region == "hand" and index in rightmost:
        return "right_edge_hand_miss"
    if region == "meld" and any(
        other_index != index and _overlap(component["pixel_bbox"], other["pixel_bbox"])
        for other_index, other in enumerate(all_components)
    ):
        return "stacked_or_overlapping_meld_miss"
    if region == "meld":
        return "meld_component_miss"
    if region == "draw_visual":
        return "draw_visual_miss"
    if region == "gold":
        return "public_gold_miss"
    return "interior_hand_miss"


def _draw_box(draw: ImageDraw.ImageDraw, box: list[int], color: str, label: str, width: int) -> None:
    x, y, box_width, box_height = box
    draw.rectangle((x, y, x + box_width, y + box_height), outline=color, width=width)
    draw.text((x, max(0, y - 13)), label, fill=color)


def analyze(dataset: Path, media_root: Path) -> dict:
    plan_path = dataset / "validation" / "holdout" / "phase5b_geometry_holdout_plan_v0_2.json"
    truth_path = dataset / "validation" / "holdout" / "geometry_holdout_ground_truth_v0_2.jsonl"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    truth = _read_rows(truth_path)
    sources = locate_sources(media_root)
    generated = dataset / "validation" / "generated" / "phase5d_error_overlays"
    generated.mkdir(parents=True, exist_ok=True)

    categories: Counter[str] = Counter()
    failures: list[dict] = []
    for item in plan["frames"]:
        row = truth[item["id"]]
        source = sources.get(row["source_sha256"])
        if source is None:
            raise ValueError(f"Missing anonymous source for {row['id']}")
        image = _frame(source, row["source_frame"])
        observation = detect_dynamic_geometry(
            image, frame=row["source_frame"], session=row["source_session"]
        )
        if row["frame_state"] != "trusted":
            rejected = observation.geometry_untrusted
            category = "non_trusted_rejected" if rejected else "non_trusted_not_rejected"
            categories[category] += 1
            failures.append({
                "id": row["id"],
                "frame_state": row["frame_state"],
                "scene_type": row.get("scene_type"),
                "geometry_untrusted": rejected,
                "categories": [category],
            })
            continue

        expected = [
            component for component in row["components"]
            if component["region_candidate"] in {"hand", "draw_visual", "gold", "meld"}
        ]
        predicted = [component.to_dict() for component in observation.components]
        matches = _match(expected, predicted)
        rightmost = _rightmost_hand_ids(expected)
        row_categories: Counter[str] = Counter()
        overlay = image.copy()
        draw = ImageDraw.Draw(overlay)
        for candidate in predicted:
            _draw_box(
                draw, candidate["pixel_bbox"], COLORS["prediction"],
                f"P:{candidate['region_candidate']}", 2,
            )
        for index, (target, candidate, _) in enumerate(matches):
            if candidate is None:
                category = _miss_category(index, target, expected, rightmost)
                row_categories[category] += 1
                _draw_box(draw, target["pixel_bbox"], COLORS["miss"], f"MISS:{target['region_candidate']}", 4)
            elif candidate["region_candidate"] != target["region_candidate"]:
                category = f"region_{target['region_candidate']}_as_{candidate['region_candidate']}"
                row_categories[category] += 1
                _draw_box(draw, target["pixel_bbox"], COLORS["region_error"], category, 4)
            else:
                _draw_box(draw, target["pixel_bbox"], COLORS["truth"], f"T:{target['region_candidate']}", 1)
        matched_prediction_ids = {id(candidate) for _, candidate, _ in matches if candidate is not None}
        unmatched_predictions = sum(id(candidate) not in matched_prediction_ids for candidate in predicted)
        if unmatched_predictions:
            row_categories["unmatched_prediction"] += unmatched_predictions
        if not row_categories:
            continue
        categories.update(row_categories)
        overlay.save(generated / f"{row['id']}.png")
        failures.append({
            "id": row["id"],
            "source_id": row["source_id"],
            "source_session": row["source_session"],
            "source_frame": row["source_frame"],
            "categories": dict(row_categories),
            "detector_issues": list(observation.issues),
        })

    report = {
        "schema_version": "vision_runtime_v0_2_phase5d_error_analysis",
        "status": "revealed_holdout_diagnostic_only",
        "policy": (
            "Phase 5C is revealed and may be used only as a regression/development set. "
            "Any generalized claim requires a new untouched blind holdout."
        ),
        "source_report": "validation/reports/phase5c_blind_holdout_validation_v0_2.json",
        "category_counts": dict(categories.most_common()),
        "failure_frames": failures,
        "local_overlay_directory": "validation/generated/phase5d_error_overlays",
        "phase6_formal_tile_labeling_allowed": False,
        "safe_for_executor": False,
    }
    output = dataset / "validation" / "reports" / "phase5d_geometry_error_analysis_v0_2.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="dataset/tiles_runtime_v0_2")
    parser.add_argument("--media-root", default="data/capture_validation")
    args = parser.parse_args()
    print(json.dumps(analyze(Path(args.dataset), Path(args.media_root)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
