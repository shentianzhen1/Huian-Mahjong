"""Metrics for independently approved V0.2 geometry truth.

Phase 5B keeps the approved truth immutable. The old review rows predate the
``meld`` region, so a correctly separated meld candidate is reported
separately rather than charged as a false positive against truth with no meld
box.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

from .dynamic_geometry import detect_dynamic_geometry, fuse_dynamic_geometry
from .geometry_schema import compatibility_view
from .geometry_review import read_frame


RUNTIME_TARGET_REGIONS = frozenset({"hand", "draw_visual", "gold"})
MELD_AUDIT_SESSION = "session_7f4c1b2e"
MELD_AUDIT_FRAMES = frozenset(range(2028, 2033))
RIGHT_EDGE_AUDIT_SESSION = "session_5d8a0e3c"
RIGHT_EDGE_AUDIT_FRAMES = frozenset(range(3335, 3340))


def iou(first, second) -> float:
    x, y, width, height = first; ox, oy, ow, oh = second
    left, top, right, bottom = max(x, ox), max(y, oy), min(x + width, ox + ow), min(y + height, oy + oh)
    overlap = max(0, right-left) * max(0, bottom-top)
    return overlap / (width*height + ow*oh - overlap) if overlap else 0.0


def _approved_rows(path: Path) -> list[dict]:
    return [
        compatibility_view(row) for row in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)
        if row.get("approved") and row.get("review_status") == "approved_geometry"
    ]


def _temporal_jitter(observations: list[tuple[dict, object]]) -> dict:
    """Measure observed centre movement and describe the current fusion mode."""
    by_session: dict[str, list[tuple[dict, object]]] = defaultdict(list)
    for row, observation in observations:
        by_session[row["source_session"]].append((row, observation))
    groups = []
    for entries in by_session.values():
        entries.sort(key=lambda item: item[0]["source_frame"])
        current, previous = [], None
        for entry in entries:
            frame = entry[0]["source_frame"]
            if previous is not None and frame != previous + 1:
                groups.append(current); current = []
            current.append(entry); previous = frame
        if current:
            groups.append(current)

    deltas, stable_windows = [], 0
    for group in groups:
        frames = [observation for _, observation in group]
        fused = fuse_dynamic_geometry(frames, minimum_frames=3) if len(frames) >= 3 else None
        stable_windows += int(fused is not None and not fused.geometry_untrusted)
        for left, right in zip(frames, frames[1:]):
            previous_by_region, current_by_region = defaultdict(list), defaultdict(list)
            for component in left.components:
                previous_by_region[component.region_candidate].append(component.pixel_bbox)
            for component in right.components:
                current_by_region[component.region_candidate].append(component.pixel_bbox)
            for region in set(previous_by_region) & set(current_by_region):
                earlier = sorted(previous_by_region[region])
                later = sorted(current_by_region[region])
                if len(earlier) != len(later):
                    continue
                for first, second in zip(earlier, later):
                    x, y, width, height = first; ox, oy, ow, oh = second
                    deltas.append(math.hypot((ox + ow / 2) - (x + width / 2), (oy + oh / 2) - (y + height / 2)))
    return {
        "adjacent_component_center_mean_px": None if not deltas else sum(deltas) / len(deltas),
        "adjacent_component_center_max_px": None if not deltas else max(deltas),
        "component_transitions": len(deltas),
        "stable_windows": stable_windows,
        "windows_with_at_least_3_frames": sum(len(group) >= 3 for group in groups),
        "fusion_coordinate_behavior": "layout-vote only; fused boxes are the selected latest trusted frame and are not spatially averaged",
    }


def _rightmost_hand_misses(row: dict, prediction: list[dict]) -> int:
    expected = sorted((component for component in row["components"] if component["region_candidate"] == "hand"), key=lambda item: item["pixel_bbox"][0])
    return sum(
        not any(
            candidate["region_candidate"] == "hand" and iou(component["pixel_bbox"], candidate["pixel_bbox"]) >= 0.5
            for candidate in prediction
        )
        for component in expected[-2:]
    )


def evaluate(dataset: Path) -> dict:
    truth_path = dataset / "validation" / "geometry_ground_truth_v0_2.jsonl"
    rows = _approved_rows(truth_path)
    truth_hash = hashlib.sha256(truth_path.read_bytes()).hexdigest()
    true_positive = false_positive = false_negative = region_errors = 0
    truth_total = primary_prediction_total = meld_candidates = 0
    ious, hand_exact, trusted, rejected = [], 0, 0, 0
    meld_as_hand = meld_candidates_in_audit = right_edge_misses = right_edge_expected = 0
    observations: list[tuple[dict, object]] = []

    for row in rows:
        image = read_frame(row["source_session"], row["source_frame"])
        observation = detect_dynamic_geometry(image, frame=row["source_frame"], session=row["source_session"])
        observations.append((row, observation))
        prediction = [component.to_dict() for component in observation.components]
        expected = [component for component in row["components"] if component["region_candidate"] in RUNTIME_TARGET_REGIONS]
        primary = [component for component in prediction if component["region_candidate"] in RUNTIME_TARGET_REGIONS]
        truth_total += len(expected)
        primary_prediction_total += len(primary)
        meld_candidates += sum(component["region_candidate"] == "meld" for component in prediction)

        # Match all regions by geometry first, then judge region correctness.
        # A wrong-region match is deliberately both a target FN and, when its
        # prediction is a runtime target, a target FP.
        used, correct_matches = set(), 0
        for component in expected:
            best = max(
                ((iou(component["pixel_bbox"], candidate["pixel_bbox"]), index)
                 for index, candidate in enumerate(prediction) if index not in used),
                default=(0.0, None),
            )
            if best[0] < 0.5:
                continue
            used.add(best[1])
            candidate = prediction[best[1]]
            if candidate["region_candidate"] == component["region_candidate"]:
                correct_matches += 1
                ious.append(best[0])
            else:
                region_errors += 1
        true_positive += correct_matches
        false_negative += len(expected) - correct_matches
        false_positive += len(primary) - correct_matches
        hand_exact += int(sum(component["region_candidate"] == "hand" for component in prediction) == row["expected_hand_region_count"])
        if row["frame_state"] == "trusted":
            trusted += 1
        elif observation.geometry_untrusted:
            rejected += 1

        if row["source_session"] == MELD_AUDIT_SESSION and row["source_frame"] in MELD_AUDIT_FRAMES:
            meld_candidates_in_audit += sum(component["region_candidate"] == "meld" for component in prediction)
            meld_as_hand += max(0, sum(component["region_candidate"] == "hand" for component in prediction) - row["expected_hand_region_count"])
        if row["source_session"] == RIGHT_EDGE_AUDIT_SESSION and row["source_frame"] in RIGHT_EDGE_AUDIT_FRAMES:
            right_edge_misses += _rightmost_hand_misses(row, prediction)
            right_edge_expected += min(2, row["expected_hand_region_count"])

    report_path = dataset / "validation" / "reports" / "phase5_real_geometry_validation_v0_2.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    report.update({
        "status": "metrics_computed_phase5b",
        "ground_truth_path": "validation/geometry_ground_truth_v0_2.jsonl",
        "ground_truth_rows_approved": len(rows),
        "ground_truth_sha256": truth_hash,
        "ground_truth_policy": "The approved rows are frozen. Metrics rerun the detector from source frames and never write the truth file.",
        "metrics_definition": {
            "runtime_target_regions": sorted(RUNTIME_TARGET_REGIONS),
            "meld": "Meld is a separate non-hand candidate. The frozen Phase 5 truth predates meld boxes, so meld candidates are reported separately and are not counted as target false positives.",
            "iou_match_threshold": 0.5,
        },
        "metrics": {
            "component_recall": None if not truth_total else true_positive / truth_total,
            "component_precision": None if not primary_prediction_total else true_positive / primary_prediction_total,
            "bbox_iou": None if not ious else sum(ious) / len(ious),
            "region_classification_accuracy": None if not true_positive + region_errors else true_positive / (true_positive + region_errors),
            "hand_count_exact_match_rate": None if not rows else hand_exact / len(rows),
            "false_positives": false_positive,
            "false_negatives": false_negative,
            "region_misclassifications": region_errors,
            "geometry_untrusted_reject_rate": None if not len(rows) - trusted else rejected / (len(rows) - trusted),
            "temporal_jitter": _temporal_jitter(observations),
        },
        "phase5b_targeted_regression": {
            "meld_candidates": meld_candidates,
            "meld_audit_frames": len(MELD_AUDIT_FRAMES),
            "meld_candidates_in_audit": meld_candidates_in_audit,
            "meld_misclassified_as_hand": meld_as_hand,
            "right_edge_audit_frames": len(RIGHT_EDGE_AUDIT_FRAMES),
            "rightmost_hand_components_checked": right_edge_expected,
            "rightmost_hand_false_negatives": right_edge_misses,
        },
        "safe_for_executor": False,
    })
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="dataset/tiles_runtime_v0_2")
    print(json.dumps(evaluate(Path(parser.parse_args().dataset)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
