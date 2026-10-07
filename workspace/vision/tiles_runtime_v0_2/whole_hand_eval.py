"""Source-disjoint whole-hand evaluation for Runtime Vision concealed identity.

This module is diagnostic only. It does not alter Runtime classification, the
frozen 0.82 confidence gate, Hint Alpha behavior, or Executor state.

A reviewed hand is represented once, with detector/crop audit fields and model
predictions attached to the same crop record. That makes template-vs-candidate
A/B comparisons use the exact same crops while keeping detector/crop failures
separate from classifier failures.

Independence is keyed by ``original_match_group``. ``source_session`` is
traceability metadata only and is never treated as proof of independence.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
from typing import Iterable


SCHEMA_VERSION = "vision_runtime_v0_2_whole_hand_eval_manifest_v0_1"
FROZEN_CONFIDENCE_THRESHOLD = 0.82
REVIEWED_COMPLETE = "reviewed_complete"
_ALLOWED_TRUTH_STATUS = frozenset({REVIEWED_COMPLETE, "partial"})
_ALLOWED_DETECTION_STATUS = frozenset({"matched", "missed"})
_ALLOWED_CROP_STATUS = frozenset(
    {"ok", "bad_crop", "shadowed", "prompt_occlusion", "unreviewed"}
)


def _nonempty_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _numeric(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def _prediction_for(slot: dict, model_name: str) -> dict | None:
    predictions = slot.get("predictions", {})
    if not isinstance(predictions, dict):
        raise ValueError("slot.predictions must be an object")
    prediction = predictions.get(model_name)
    if prediction is None:
        return None
    if not isinstance(prediction, dict):
        raise ValueError(f"prediction for {model_name!r} must be an object")
    tile_id = _nonempty_text(
        prediction.get("tile_id"),
        f"prediction[{model_name}].tile_id",
    )
    confidence = _numeric(
        prediction.get("confidence"),
        f"prediction[{model_name}].confidence",
    )
    if not 0.0 <= confidence <= 1.0:
        raise ValueError(
            f"prediction[{model_name}].confidence must be between 0 and 1"
        )
    return {"tile_id": tile_id, "confidence": confidence}


def _percentile(values: Iterable[float], q: float) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def validate_manifest(manifest: dict) -> None:
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")

    threshold = _numeric(
        manifest.get("confidence_threshold"),
        "confidence_threshold",
    )
    if not math.isclose(
        threshold,
        FROZEN_CONFIDENCE_THRESHOLD,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError(
            "confidence_threshold is frozen at "
            f"{FROZEN_CONFIDENCE_THRESHOLD:.2f}; this evaluator does not tune it"
        )

    hands = manifest.get("hands")
    if not isinstance(hands, list):
        raise ValueError("hands must be an array")

    seen_samples: set[str] = set()
    match_splits: dict[str, str] = {}
    for hand_index, hand in enumerate(hands):
        if not isinstance(hand, dict):
            raise ValueError(f"hands[{hand_index}] must be an object")
        sample_id = _nonempty_text(
            hand.get("sample_id"),
            f"hands[{hand_index}].sample_id",
        )
        if sample_id in seen_samples:
            raise ValueError(f"duplicate sample_id: {sample_id}")
        seen_samples.add(sample_id)

        split = _nonempty_text(
            hand.get("split"),
            f"hands[{hand_index}].split",
        )
        original_match_group = _nonempty_text(
            hand.get("original_match_group"),
            f"hands[{hand_index}].original_match_group",
        )
        previous_split = match_splits.setdefault(original_match_group, split)
        if previous_split != split:
            raise ValueError(
                "source leakage: original_match_group "
                f"{original_match_group!r} occurs in both "
                f"{previous_split!r} and {split!r}"
            )

        _nonempty_text(
            hand.get("source_session"),
            f"hands[{hand_index}].source_session",
        )
        _nonempty_text(hand.get("game_id"), f"hands[{hand_index}].game_id")

        truth_status = hand.get("truth_status")
        if truth_status not in _ALLOWED_TRUTH_STATUS:
            raise ValueError(
                f"hands[{hand_index}].truth_status must be one of "
                f"{sorted(_ALLOWED_TRUTH_STATUS)}"
            )

        slots = hand.get("slots")
        if not isinstance(slots, list) or not slots:
            raise ValueError(f"hands[{hand_index}].slots must be a non-empty array")
        slot_ids: set[int] = set()
        for slot_index, slot in enumerate(slots):
            if not isinstance(slot, dict):
                raise ValueError(
                    f"hands[{hand_index}].slots[{slot_index}] must be an object"
                )
            slot_id = slot.get("slot")
            if isinstance(slot_id, bool) or not isinstance(slot_id, int) or slot_id < 0:
                raise ValueError(
                    f"hands[{hand_index}].slots[{slot_index}].slot "
                    "must be a non-negative integer"
                )
            if slot_id in slot_ids:
                raise ValueError(
                    f"hands[{hand_index}] has duplicate slot index {slot_id}"
                )
            slot_ids.add(slot_id)
            _nonempty_text(
                slot.get("truth_tile"),
                f"hands[{hand_index}].slots[{slot_index}].truth_tile",
            )
            detection_status = slot.get("detection_status")
            if detection_status not in _ALLOWED_DETECTION_STATUS:
                raise ValueError(
                    f"hands[{hand_index}].slots[{slot_index}].detection_status "
                    f"must be one of {sorted(_ALLOWED_DETECTION_STATUS)}"
                )
            crop_status = slot.get("crop_status")
            if crop_status not in _ALLOWED_CROP_STATUS:
                raise ValueError(
                    f"hands[{hand_index}].slots[{slot_index}].crop_status "
                    f"must be one of {sorted(_ALLOWED_CROP_STATUS)}"
                )
            if detection_status == "missed":
                if slot.get("crop_ref") is not None:
                    raise ValueError(
                        f"hands[{hand_index}].slots[{slot_index}] is missed "
                        "but has crop_ref"
                    )
                if slot.get("predictions"):
                    raise ValueError(
                        f"hands[{hand_index}].slots[{slot_index}] is missed "
                        "but has classifier predictions"
                    )
            else:
                _nonempty_text(
                    slot.get("crop_ref"),
                    f"hands[{hand_index}].slots[{slot_index}].crop_ref",
                )

        extras = hand.get("extra_detections", [])
        if not isinstance(extras, list):
            raise ValueError(f"hands[{hand_index}].extra_detections must be an array")
        for extra_index, extra in enumerate(extras):
            if not isinstance(extra, dict):
                raise ValueError(
                    f"hands[{hand_index}].extra_detections[{extra_index}] "
                    "must be an object"
                )
            _nonempty_text(
                extra.get("crop_ref"),
                f"hands[{hand_index}].extra_detections[{extra_index}].crop_ref",
            )

        latency = hand.get("capture_to_advice_ms", {})
        if not isinstance(latency, dict):
            raise ValueError(
                f"hands[{hand_index}].capture_to_advice_ms must be an object"
            )
        for model_name, value in latency.items():
            _nonempty_text(model_name, "capture_to_advice_ms model name")
            latency_value = _numeric(
                value,
                f"hands[{hand_index}].capture_to_advice_ms[{model_name}]",
            )
            if latency_value < 0:
                raise ValueError("capture_to_advice_ms cannot be negative")


def _eligible_hands(manifest: dict) -> tuple[list[dict], int]:
    hands = manifest["hands"]
    eligible = [
        hand for hand in hands if hand.get("truth_status") == REVIEWED_COMPLETE
    ]
    return eligible, len(hands) - len(eligible)


def _require_same_crop_prediction_coverage(
    hands: Iterable[dict],
    model_names: Iterable[str],
) -> None:
    names = tuple(model_names)
    for hand in hands:
        for slot in hand["slots"]:
            if slot["detection_status"] != "matched":
                continue
            crop_ref = slot["crop_ref"]
            missing = [
                model_name
                for model_name in names
                if _prediction_for(slot, model_name) is None
            ]
            if missing:
                raise ValueError(
                    "classifier A/B requires predictions from every compared model "
                    f"on the exact same matched crop; sample={hand['sample_id']!r}, "
                    f"crop_ref={crop_ref!r}, missing={missing}"
                )


def evaluate_model(manifest: dict, model_name: str) -> dict:
    validate_manifest(manifest)
    model_name = _nonempty_text(model_name, "model_name")
    hands, excluded_partial = _eligible_hands(manifest)

    tile_truth = 0
    raw_predictions = 0
    raw_correct = 0
    accepted_predictions = 0
    accepted_correct = 0
    rejected_tiles = 0
    missed_detections = 0
    extra_detections = 0
    crop_status_counts: Counter[str] = Counter()
    primary_outcomes: Counter[str] = Counter()
    confusion_pairs: Counter[str] = Counter()
    exact_hands = 0
    advice_eligible_hands = 0
    wrong_accepted_hands = 0
    blocked_hands = 0
    latency_values: list[float] = []

    per_hand = []
    for hand in hands:
        expected_tiles = []
        accepted_tiles = []
        hand_blocked = False
        for slot in sorted(hand["slots"], key=lambda row: row["slot"]):
            truth_tile = slot["truth_tile"]
            expected_tiles.append(truth_tile)
            tile_truth += 1

            if slot["detection_status"] == "missed":
                missed_detections += 1
                rejected_tiles += 1
                primary_outcomes["missed_detection"] += 1
                hand_blocked = True
                continue

            crop_status = slot["crop_status"]
            crop_status_counts[crop_status] += 1
            prediction = _prediction_for(slot, model_name)
            if prediction is None:
                rejected_tiles += 1
                primary_outcomes["rejected_missing_prediction"] += 1
                hand_blocked = True
                continue

            raw_predictions += 1
            raw_is_correct = prediction["tile_id"] == truth_tile
            raw_correct += int(raw_is_correct)

            accepted = prediction["confidence"] >= FROZEN_CONFIDENCE_THRESHOLD
            if not accepted:
                rejected_tiles += 1
                if crop_status == "bad_crop":
                    primary_outcomes["bad_crop"] += 1
                elif crop_status == "shadowed":
                    primary_outcomes["shadowed"] += 1
                elif crop_status == "prompt_occlusion":
                    primary_outcomes["prompt_occlusion"] += 1
                else:
                    primary_outcomes["rejected_below_threshold"] += 1
                hand_blocked = True
                continue

            accepted_predictions += 1
            accepted_tiles.append(prediction["tile_id"])
            if raw_is_correct:
                accepted_correct += 1
                if crop_status == "bad_crop":
                    primary_outcomes["bad_crop_but_correct"] += 1
                elif crop_status == "shadowed":
                    primary_outcomes["shadowed_but_correct"] += 1
                elif crop_status == "prompt_occlusion":
                    primary_outcomes["prompt_occlusion_but_correct"] += 1
                else:
                    primary_outcomes["correct"] += 1
            else:
                confusion_pairs[f"{truth_tile}->{prediction['tile_id']}"] += 1
                if crop_status == "bad_crop":
                    primary_outcomes["bad_crop"] += 1
                elif crop_status == "shadowed":
                    primary_outcomes["shadowed"] += 1
                elif crop_status == "prompt_occlusion":
                    primary_outcomes["prompt_occlusion"] += 1
                else:
                    primary_outcomes["class_confusion"] += 1

        extras = len(hand.get("extra_detections", []))
        extra_detections += extras
        if extras:
            primary_outcomes["extra_detection"] += extras
            hand_blocked = True

        exact = (
            not hand_blocked
            and Counter(accepted_tiles) == Counter(expected_tiles)
            and len(accepted_tiles) == len(expected_tiles)
        )
        advice_eligible = not hand_blocked and len(accepted_tiles) == len(expected_tiles)
        if exact:
            exact_hands += 1
        if advice_eligible:
            advice_eligible_hands += 1
            if not exact:
                wrong_accepted_hands += 1
        else:
            blocked_hands += 1

        latency = hand.get("capture_to_advice_ms", {}).get(model_name)
        if latency is not None:
            latency_values.append(float(latency))

        per_hand.append(
            {
                "sample_id": hand["sample_id"],
                "split": hand["split"],
                "original_match_group": hand["original_match_group"],
                "game_id": hand["game_id"],
                "truth_tile_count": len(expected_tiles),
                "advice_eligible": advice_eligible,
                "whole_hand_exact": exact,
                "wrong_accepted_hand": bool(advice_eligible and not exact),
                "extra_detection_count": extras,
            }
        )

    total_hands = len(hands)
    return {
        "schema_version": "vision_runtime_v0_2_whole_hand_eval_report_v0_1",
        "model": model_name,
        "confidence_threshold": FROZEN_CONFIDENCE_THRESHOLD,
        "confidence_threshold_frozen": True,
        "source_independence_key": "original_match_group",
        "source_session_is_independence_signal": False,
        "reviewed_complete_hands": total_hands,
        "excluded_partial_hands": excluded_partial,
        "truth_tiles": tile_truth,
        "raw_predicted_tiles": raw_predictions,
        "raw_tile_accuracy": raw_correct / raw_predictions if raw_predictions else None,
        "accepted_tiles": accepted_predictions,
        "accepted_tile_accuracy": (
            accepted_correct / accepted_predictions if accepted_predictions else None
        ),
        "tile_reject_rate": rejected_tiles / tile_truth if tile_truth else None,
        "missed_detection_count": missed_detections,
        "extra_detection_count": extra_detections,
        "crop_status_counts": dict(sorted(crop_status_counts.items())),
        "primary_outcomes": dict(sorted(primary_outcomes.items())),
        "class_confusions": dict(
            sorted(confusion_pairs.items(), key=lambda item: (-item[1], item[0]))
        ),
        "whole_hand_exact_count": exact_hands,
        "whole_hand_exact_rate": exact_hands / total_hands if total_hands else None,
        "advice_eligible_hand_count": advice_eligible_hands,
        "advice_eligible_hand_rate": (
            advice_eligible_hands / total_hands if total_hands else None
        ),
        "wrong_accepted_hand_count": wrong_accepted_hands,
        "wrong_accepted_hand_rate": (
            wrong_accepted_hands / total_hands if total_hands else None
        ),
        "blocked_hand_count": blocked_hands,
        "latency_ms": {
            "count": len(latency_values),
            "p50": _percentile(latency_values, 0.50),
            "p95": _percentile(latency_values, 0.95),
        },
        "hands": per_hand,
        "diagnostic_only": True,
        "changes_runtime_behavior": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def compare_models(
    manifest: dict,
    baseline_model: str,
    candidate_model: str,
) -> dict:
    validate_manifest(manifest)
    baseline_model = _nonempty_text(baseline_model, "baseline_model")
    candidate_model = _nonempty_text(candidate_model, "candidate_model")
    if baseline_model == candidate_model:
        raise ValueError("baseline_model and candidate_model must be different")

    hands, _ = _eligible_hands(manifest)
    _require_same_crop_prediction_coverage(
        hands,
        (baseline_model, candidate_model),
    )
    baseline = evaluate_model(manifest, baseline_model)
    candidate = evaluate_model(manifest, candidate_model)

    delta_keys = (
        "raw_tile_accuracy",
        "accepted_tile_accuracy",
        "tile_reject_rate",
        "whole_hand_exact_rate",
        "advice_eligible_hand_rate",
        "wrong_accepted_hand_rate",
    )
    deltas = {}
    for key in delta_keys:
        before = baseline[key]
        after = candidate[key]
        deltas[key] = (
            after - before if before is not None and after is not None else None
        )

    return {
        "schema_version": "vision_runtime_v0_2_whole_hand_ab_report_v0_1",
        "confidence_threshold": FROZEN_CONFIDENCE_THRESHOLD,
        "same_manifest": True,
        "same_matched_crop_requirement": True,
        "source_independence_key": "original_match_group",
        "baseline_model": baseline_model,
        "candidate_model": candidate_model,
        "baseline": baseline,
        "candidate": candidate,
        "candidate_minus_baseline": deltas,
        "diagnostic_only": True,
        "changes_runtime_behavior": False,
    }


def load_manifest(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_manifest(payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate reviewed whole-hand Runtime identity without changing "
            "the frozen 0.82 gate"
        )
    )
    parser.add_argument("manifest")
    parser.add_argument("--model", required=True)
    parser.add_argument("--candidate-model")
    parser.add_argument("--output")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    if args.candidate_model:
        report = compare_models(
            manifest,
            baseline_model=args.model,
            candidate_model=args.candidate_model,
        )
    else:
        report = evaluate_model(manifest, args.model)

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
