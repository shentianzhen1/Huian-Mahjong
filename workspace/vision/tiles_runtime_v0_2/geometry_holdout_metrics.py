"""One-shot Phase 5C evaluation after blind geometry review is complete."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import cv2
from PIL import Image

from .dynamic_geometry import detect_dynamic_geometry
from .geometry_schema import compatibility_view
from .geometry_metrics import iou
from .phase5b_holdout import locate_sources


REGIONS = frozenset({"hand", "draw_visual", "gold", "meld"})
RUNTIME_REGIONS = frozenset({"hand", "draw_visual", "gold"})
IOU_THRESHOLD = 0.5


def _rows(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    return {
        row["id"]: compatibility_view(row)
        for row in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)
    }


def _frame(source: Path, number: int) -> Image.Image:
    capture = cv2.VideoCapture(str(source))
    capture.set(cv2.CAP_PROP_POS_FRAMES, number)
    ok, frame = capture.read()
    capture.release()
    if not ok:
        raise ValueError("A locally available blind-holdout frame could not be read")
    return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))


def _match(expected: list[dict], predicted: list[dict]) -> list[tuple[dict, dict | None, float]]:
    used, matches = set(), []
    for component in expected:
        score, index = max(
            ((iou(component["pixel_bbox"], candidate["pixel_bbox"]), candidate_index)
             for candidate_index, candidate in enumerate(predicted) if candidate_index not in used),
            default=(0.0, None),
        )
        if score >= IOU_THRESHOLD:
            used.add(index)
            matches.append((component, predicted[index], score))
        else:
            matches.append((component, None, 0.0))
    return matches


def evaluate(dataset: Path, plan_path: Path, truth_path: Path, sources: dict[str, Path]) -> dict:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    expected_ids = {item["id"] for item in plan["frames"]}
    truth = _rows(truth_path)
    unapproved = sorted(
        item_id for item_id in expected_ids
        if not truth.get(item_id, {}).get("approved")
        or truth[item_id].get("review_status") != "approved_geometry"
    )
    if unapproved:
        raise ValueError(f"Blind holdout is incomplete: {len(unapproved)} frame(s) are not manually approved")
    if set(truth) != expected_ids:
        raise ValueError("Blind holdout truth IDs do not exactly match the locked holdout plan")

    matched = predicted_total = truth_total = correct_regions = 0
    hand_exact = meld_as_hand = runtime_region_misclassifications = 0
    draw_visual_gold_silent_misclassifications = draw_visual_gold_unknown = 0
    ious, cases, state_counts, rejected = [], [], Counter(), 0
    for item in plan["frames"]:
        row = truth[item["id"]]
        state_counts[row["frame_state"]] += 1
        source = sources.get(row["source_sha256"])
        if source is None:
            raise ValueError("A local source matching an anonymous holdout ID is missing")
        observation = detect_dynamic_geometry(_frame(source, row["source_frame"]), frame=row["source_frame"], session=row["source_session"])
        expected = [component for component in row["components"] if component["region_candidate"] in REGIONS]
        prediction = [component.to_dict() for component in observation.components]
        truth_total += len(expected)
        predicted_total += len(prediction)
        rejected += int(observation.geometry_untrusted)
        row_matched = row_region_errors = row_meld_as_hand = 0
        for target, candidate, score in _match(expected, prediction):
            if candidate is None:
                continue
            matched += 1
            ious.append(score)
            row_matched += 1
            if candidate["region_candidate"] == target["region_candidate"]:
                correct_regions += 1
                continue
            row_region_errors += 1
            if target["region_candidate"] == "meld" and candidate["region_candidate"] == "hand":
                meld_as_hand += 1
                row_meld_as_hand += 1
            if target["region_candidate"] in RUNTIME_REGIONS and candidate["region_candidate"] != "unknown":
                runtime_region_misclassifications += 1
            if target["region_candidate"] in {"draw_visual", "gold"}:
                if candidate["region_candidate"] == "unknown":
                    draw_visual_gold_unknown += 1
                else:
                    draw_visual_gold_silent_misclassifications += 1
        hand_exact += int(sum(component["region_candidate"] == "hand" for component in prediction) == row["expected_hand_region_count"])
        if row_matched != len(expected) or len(prediction) != len(expected) or row_region_errors:
            cases.append({
                "id": row["id"], "source_id": row["source_id"], "source_session": row["source_session"], "source_frame": row["source_frame"],
                "truth_components": len(expected), "detected_components": len(prediction),
                "matched_components": row_matched, "region_errors": row_region_errors,
                "meld_as_hand": row_meld_as_hand, "geometry_untrusted": observation.geometry_untrusted,
                "issues": list(observation.issues),
            })

    precision = None if not predicted_total else matched / predicted_total
    recall = None if not truth_total else matched / truth_total
    region_accuracy = None if not matched else correct_regions / matched
    hand_count_exact = hand_exact / len(plan["frames"])
    gates = {
        "component_precision_minimum": {"threshold": 0.98, "actual": precision, "passed": precision is not None and precision >= 0.98},
        "component_recall_minimum": {"threshold": 0.98, "actual": recall, "passed": recall is not None and recall >= 0.98},
        "hand_count_exact_minimum": {"threshold": 0.95, "actual": hand_count_exact, "passed": hand_count_exact >= 0.95},
        "no_silent_hand_draw_visual_gold_region_misclassification": {"actual": runtime_region_misclassifications, "passed": runtime_region_misclassifications == 0},
        "meld_never_classified_as_hand": {"actual": meld_as_hand, "passed": meld_as_hand == 0},
    }
    passed = all(gate["passed"] for gate in gates.values())
    report = {
        "schema_version": "vision_runtime_v0_2_phase5c_blind_holdout",
        "status": "metrics_computed",
        "evaluation_policy": "The locked blind-holdout truth was fully approved before this one-shot detector run. No holdout outcome authorizes detector tuning in this phase.",
        "plan": "validation/holdout/phase5b_geometry_holdout_plan_v0_2.json",
        "truth": "validation/holdout/geometry_holdout_ground_truth_v0_2.jsonl",
        "approved_rows": len(plan["frames"]),
        "truth_state_counts": dict(state_counts),
        "metrics": {
            "component_precision": precision,
            "component_recall": recall,
            "bbox_mean_iou": None if not ious else sum(ious) / len(ious),
            "region_accuracy": region_accuracy,
            "hand_count_exact_match_rate": hand_count_exact,
            "false_positives": predicted_total - matched,
            "false_negatives": truth_total - matched,
            "meld_misclassified_as_hand": meld_as_hand,
            "draw_visual_gold_silent_misclassifications": draw_visual_gold_silent_misclassifications,
            "draw_visual_gold_unknown": draw_visual_gold_unknown,
            "geometry_untrusted_frames": rejected,
        },
        "acceptance_gates": gates,
        "failure_cases": cases,
        "coverage_gaps": {
            "second_960x448_session": "not_found_locally; retained but no longer a Phase 6 blocker",
            "17_hand": "not independently reviewed; retained but no longer a Phase 6 blocker",
        },
        "phase6_formal_tile_labeling_allowed": passed,
        "safe_for_executor": False,
    }
    output = dataset / "validation" / "reports" / "phase5c_blind_holdout_validation_v0_2.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a fully approved Phase 5C blind holdout once")
    parser.add_argument("--dataset", default="dataset/tiles_runtime_v0_2")
    parser.add_argument("--plan", default="dataset/tiles_runtime_v0_2/validation/holdout/phase5b_geometry_holdout_plan_v0_2.json")
    parser.add_argument("--truth", default="dataset/tiles_runtime_v0_2/validation/holdout/geometry_holdout_ground_truth_v0_2.jsonl")
    parser.add_argument("--media-root", default="data/capture_validation")
    args = parser.parse_args()
    print(json.dumps(evaluate(Path(args.dataset), Path(args.plan), Path(args.truth), locate_sources(Path(args.media_root))), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
