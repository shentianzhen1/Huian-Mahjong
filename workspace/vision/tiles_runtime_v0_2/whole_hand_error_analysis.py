"""Raw whole-hand classifier error analysis at the frozen Runtime threshold.

This helper complements :mod:`whole_hand_eval` by reporting *all* top-1
confusions, including wrong predictions that are later rejected below 0.82.
That distinction matters when selecting a replacement classifier: fail-closed
Runtime behavior can hide weak class boundaries from accepted-error metrics.

The input manifest remains source-disjoint by ``original_match_group`` through
``validate_manifest``.  This module is diagnostic only and changes no Runtime,
Hint Alpha, Agent, or Executor behavior.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from .whole_hand_eval import REVIEWED_COMPLETE, validate_manifest


def analyze_raw_confusions(manifest: dict, model_name: str) -> dict:
    """Return raw top-1 confusion counts before the 0.82 accept/reject gate."""
    validate_manifest(manifest)
    if not isinstance(model_name, str) or not model_name.strip():
        raise ValueError("model_name must be a non-empty string")
    model_name = model_name.strip()

    total = 0
    correct = 0
    confusion_pairs: Counter[str] = Counter()
    confusions_by_crop_status: dict[str, Counter[str]] = defaultdict(Counter)
    truth_support: Counter[str] = Counter()

    for hand in manifest["hands"]:
        if hand.get("truth_status") != REVIEWED_COMPLETE:
            continue
        for slot in hand["slots"]:
            if slot.get("detection_status") != "matched":
                continue
            prediction = slot.get("predictions", {}).get(model_name)
            if not isinstance(prediction, dict):
                continue
            tile_id = prediction.get("tile_id")
            confidence = prediction.get("confidence")
            if not isinstance(tile_id, str) or not tile_id:
                continue
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
                continue

            truth = slot["truth_tile"]
            crop_status = slot["crop_status"]
            total += 1
            truth_support[truth] += 1
            if tile_id == truth:
                correct += 1
                continue

            pair = f"{truth}->{tile_id}"
            confusion_pairs[pair] += 1
            confusions_by_crop_status[crop_status][pair] += 1

    ordered_pairs = dict(
        sorted(confusion_pairs.items(), key=lambda item: (-item[1], item[0]))
    )
    ordered_by_status = {
        status: dict(sorted(rows.items(), key=lambda item: (-item[1], item[0])))
        for status, rows in sorted(confusions_by_crop_status.items())
    }
    return {
        "schema_version": "vision_runtime_v0_2_whole_hand_raw_confusions_v0_1",
        "model": model_name,
        "raw_predicted_tiles": total,
        "raw_correct_tiles": correct,
        "raw_tile_accuracy": correct / total if total else None,
        "raw_class_confusions": ordered_pairs,
        "raw_confusions_by_crop_status": ordered_by_status,
        "truth_class_support": dict(sorted(truth_support.items())),
        "source_independence_key": "original_match_group",
        "diagnostic_only": True,
        "changes_runtime_behavior": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }
