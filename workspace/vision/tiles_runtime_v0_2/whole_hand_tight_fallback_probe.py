"""Development-only whole-hand probe for a primary-first tight-crop fallback.

This evaluator reuses a private ``whole_hand_baseline_export.py`` output and a
caller-provided candidate dataset. Runtime behavior is not changed. The frozen
0.82 identity gate remains authoritative: an identity accepted by the primary
Runtime crop is never replaced, and the tight detector crop is consulted only
when the primary identity is UNKNOWN.

The probe is intentionally not promotion evidence. A fresh original-match
batch, source-qualified support, and the repository promotion gate are still
required before any Runtime wiring.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .whole_hand_eval import FROZEN_CONFIDENCE_THRESHOLD


SCHEMA_VERSION = "concealed_primary_tight_fallback_probe_v0_1"
_BASELINE_SCHEMA = "vision_runtime_v0_2_whole_hand_baseline_export_v0_1"


def relative_tight_box(
    pixel_bbox: list[int] | tuple[int, int, int, int],
    classification_crop_bbox: list[int] | tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    """Return the detector tile box relative to its saved primary crop.

    Fail closed if the detector box is not wholly contained in the saved
    primary classification crop. This avoids silently inventing pixels that
    were not present in the private baseline export.
    """
    px, py, pw, ph = (int(value) for value in pixel_bbox)
    cx, cy, cw, ch = (int(value) for value in classification_crop_bbox)
    if min(pw, ph, cw, ch) <= 0:
        raise ValueError("crop dimensions must be positive")
    left = px - cx
    top = py - cy
    if left < 0 or top < 0 or left + pw > cw or top + ph > ch:
        raise ValueError("pixel_bbox must be contained in classification_crop_bbox")
    return left, top, pw, ph


def primary_first_identity(primary_tile_id: str, fallback_tile_id: str) -> str:
    """Never override a primary Runtime identity that already passed its gate."""
    if not isinstance(primary_tile_id, str) or not primary_tile_id:
        raise ValueError("primary_tile_id is required")
    if not isinstance(fallback_tile_id, str) or not fallback_tile_id:
        raise ValueError("fallback_tile_id is required")
    return primary_tile_id if primary_tile_id != "UNKNOWN" else fallback_tile_id


def _load_baseline(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("schema_version") != _BASELINE_SCHEMA:
        raise ValueError(f"baseline export schema must be {_BASELINE_SCHEMA!r}")
    threshold = float(report.get("confidence_threshold"))
    if abs(threshold - FROZEN_CONFIDENCE_THRESHOLD) > 1e-12:
        raise ValueError(
            f"baseline confidence threshold must remain {FROZEN_CONFIDENCE_THRESHOLD:.2f}"
        )
    if not report.get("confidence_threshold_frozen"):
        raise ValueError("baseline export must mark the confidence threshold frozen")
    source = report.get("source")
    if not isinstance(source, dict) or not isinstance(source.get("sha256"), str):
        raise ValueError("baseline export must retain source SHA256")
    if not isinstance(report.get("original_match_group"), str) or not report["original_match_group"]:
        raise ValueError("baseline export must retain original_match_group")
    if not isinstance(report.get("samples"), list) or not report["samples"]:
        raise ValueError("baseline export must contain samples")
    return report


def _sample_private_crop_path(baseline_path: Path, sample_id: str, crop_ref: str) -> Path:
    return baseline_path.parent / "crops" / sample_id / crop_ref


def probe_primary_first_tight_fallback(
    baseline_export_path: str | Path,
    dataset_root: str | Path,
    *,
    support_original_match_groups: list[str] | tuple[str, ...],
) -> dict[str, Any]:
    """Evaluate the frozen fallback policy on a private whole-hand export.

    The baseline export must already have been generated with the same candidate
    dataset that is passed here, so the primary observations are the candidate
    Runtime path. The tight crop is derived from each saved primary crop only
    for primary UNKNOWN identities.
    """
    from PIL import Image

    from .runtime_reader import (
        CONCEALED_IDENTITY_GATE_REGION,
        identity_gate,
        prepare_runtime_resources,
    )

    baseline_path = Path(baseline_export_path)
    dataset_root = Path(dataset_root)
    baseline = _load_baseline(baseline_path)
    query_group = baseline["original_match_group"]
    support_groups = tuple(
        dict.fromkeys(
            str(group).strip()
            for group in support_original_match_groups
            if str(group).strip()
        )
    )
    if not support_groups:
        raise ValueError("at least one support_original_match_group is required")
    if query_group in support_groups:
        raise ValueError("query original_match_group must not also be declared support")

    source_sha = baseline["source"]["sha256"].lower()
    session = "whole_hand_" + source_sha[:16]
    resources = prepare_runtime_resources(dataset_root, session=session)
    classifier = resources["classifier"]
    covered_by_region = resources["covered_by_region"]
    cross_session = resources["cross_session"]

    totals = {
        "truth_tiles": 0,
        "accepted_correct": 0,
        "wrong_accepted": 0,
        "rejected": 0,
        "primary_accepted": 0,
        "fallback_attempted": 0,
        "fallback_accepted": 0,
        "fallback_correct": 0,
        "fallback_wrong": 0,
    }
    complete_hands = 0
    wrong_accepted_hands = 0
    blocked_hands = 0
    per_sample: list[dict[str, Any]] = []

    for sample in baseline["samples"]:
        sample_id = str(sample.get("sample_id") or "")
        if not sample_id:
            raise ValueError("sample_id is required")
        alignment = sample.get("alignment")
        if not isinstance(alignment, dict):
            raise ValueError(f"sample {sample_id!r} has no alignment")
        slots = alignment.get("slots")
        if (
            alignment.get("status") == "manual_alignment_required"
            or not isinstance(slots, list)
            or not slots
        ):
            per_sample.append(
                {
                    "sample_id": sample_id,
                    "status": "BLOCKED_ALIGNMENT",
                    "whole_hand_complete": False,
                    "wrong_accepted_hand": False,
                    "slots": [],
                }
            )
            blocked_hands += 1
            continue

        truth = sample.get("truth") if isinstance(sample.get("truth"), dict) else {}
        if truth.get("gold_skinned_draw"):
            per_sample.append(
                {
                    "sample_id": sample_id,
                    "status": "BLOCKED_GOLD_SKIN_OUT_OF_SCOPE",
                    "whole_hand_complete": False,
                    "wrong_accepted_hand": False,
                    "slots": [],
                }
            )
            blocked_hands += 1
            continue

        final_slots: list[dict[str, Any]] = []
        hand_has_reject = False
        hand_has_wrong = False
        for slot in slots:
            truth_tile = str(slot.get("truth_tile") or "")
            primary_tile = str(slot.get("accepted_tile_id") or "UNKNOWN")
            primary_conf = float(slot.get("confidence") or 0.0)
            totals["truth_tiles"] += 1
            item: dict[str, Any] = {
                "slot": slot.get("slot"),
                "region": slot.get("region"),
                "truth_tile": truth_tile,
                "primary_tile_id": primary_tile,
                "primary_confidence": primary_conf,
                "fallback_attempted": False,
                "fallback_candidate_tile_id": None,
                "fallback_tile_id": "UNKNOWN",
                "fallback_confidence": 0.0,
                "fallback_reason": "primary_already_accepted",
            }

            if primary_tile != "UNKNOWN":
                totals["primary_accepted"] += 1
                final_tile = primary_tile
            else:
                totals["fallback_attempted"] += 1
                item["fallback_attempted"] = True
                pixel_bbox = slot.get("pixel_bbox")
                primary_bbox = slot.get("classification_crop_bbox")
                crop_ref = slot.get("private_crop_ref")
                if (
                    not pixel_bbox
                    or not primary_bbox
                    or not isinstance(crop_ref, str)
                    or not crop_ref
                ):
                    item["fallback_reason"] = "missing_private_crop_geometry"
                    final_tile = "UNKNOWN"
                else:
                    crop_path = _sample_private_crop_path(
                        baseline_path, sample_id, crop_ref
                    )
                    if not crop_path.is_file():
                        item["fallback_reason"] = "missing_private_crop_file"
                        final_tile = "UNKNOWN"
                    else:
                        try:
                            left, top, width, height = relative_tight_box(
                                pixel_bbox, primary_bbox
                            )
                            with Image.open(crop_path) as primary_crop:
                                tight = primary_crop.convert("RGB").crop(
                                    (left, top, left + width, top + height)
                                )
                            prediction = classifier.classify(
                                tight,
                                region=CONCEALED_IDENTITY_GATE_REGION,
                            )
                            fallback_tile, reason = identity_gate(
                                prediction.tile_id,
                                prediction.confidence,
                                region=CONCEALED_IDENTITY_GATE_REGION,
                                covered_classes=covered_by_region.get(
                                    CONCEALED_IDENTITY_GATE_REGION, set()
                                ),
                                cross_session_classes=cross_session,
                                confidence_threshold=FROZEN_CONFIDENCE_THRESHOLD,
                            )
                            item.update(
                                {
                                    "fallback_candidate_tile_id": prediction.tile_id,
                                    "fallback_tile_id": fallback_tile,
                                    "fallback_confidence": round(
                                        float(prediction.confidence), 6
                                    ),
                                    "fallback_reason": reason,
                                }
                            )
                            final_tile = fallback_tile
                            if fallback_tile != "UNKNOWN":
                                totals["fallback_accepted"] += 1
                                if fallback_tile == truth_tile:
                                    totals["fallback_correct"] += 1
                                else:
                                    totals["fallback_wrong"] += 1
                        except (OSError, ValueError) as exc:
                            item["fallback_reason"] = (
                                f"fallback_unavailable:{type(exc).__name__}"
                            )
                            final_tile = "UNKNOWN"

            final_tile = primary_first_identity(primary_tile, final_tile)
            item["final_tile_id"] = final_tile
            if final_tile == "UNKNOWN":
                totals["rejected"] += 1
                hand_has_reject = True
            elif final_tile == truth_tile:
                totals["accepted_correct"] += 1
            else:
                totals["wrong_accepted"] += 1
                hand_has_wrong = True
            final_slots.append(item)

        complete = not hand_has_reject and not hand_has_wrong
        wrong_accepted_hand = not hand_has_reject and hand_has_wrong
        if complete:
            complete_hands += 1
        elif wrong_accepted_hand:
            wrong_accepted_hands += 1
        else:
            blocked_hands += 1
        per_sample.append(
            {
                "sample_id": sample_id,
                "status": (
                    "COMPLETE"
                    if complete
                    else ("WRONG_ACCEPTED" if wrong_accepted_hand else "BLOCKED")
                ),
                "whole_hand_complete": complete,
                "wrong_accepted_hand": wrong_accepted_hand,
                "slots": final_slots,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "DEVELOPMENT_ONLY_NOT_RUNTIME_PROMOTION",
        "query_original_match_group": query_group,
        "support_original_match_groups": list(support_groups),
        "query_group_not_declared_support": True,
        "source_session_is_independence_signal": False,
        "confidence_threshold": FROZEN_CONFIDENCE_THRESHOLD,
        "confidence_threshold_frozen": True,
        "policy": {
            "primary_runtime_identity_is_never_overridden": True,
            "fallback_only_when_primary_unknown": True,
            "fallback_uses_tight_detector_pixel_bbox": True,
            "fallback_must_pass_existing_identity_gate": True,
            "tile_class_specific_override": False,
        },
        "totals": totals,
        "whole_hands": {
            "complete": complete_hands,
            "wrong_accepted": wrong_accepted_hands,
            "blocked": blocked_hands,
            "total": len(per_sample),
        },
        "samples": per_sample,
        "runtime_changed": False,
        "safe_for_runtime": False,
        "safe_for_hint_promotion": False,
        "safe_for_executor": False,
        "formal_promotion_evidence": False,
        "next_gate": (
            "Run this frozen policy on a fresh original-match whole-hand batch that was not used "
            "for support or tuning, then evaluate through the repository promotion gate."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe primary-first tight-crop fallback on a private whole-hand export"
    )
    parser.add_argument("baseline_export")
    parser.add_argument("--dataset", required=True)
    parser.add_argument(
        "--support-original-match-group", action="append", required=True
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = probe_primary_first_tight_fallback(
        args.baseline_export,
        args.dataset,
        support_original_match_groups=args.support_original_match_group,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "schema_version": report["schema_version"],
                "whole_hands": report["whole_hands"],
                "accepted_correct": report["totals"]["accepted_correct"],
                "wrong_accepted": report["totals"]["wrong_accepted"],
                "rejected": report["totals"]["rejected"],
                "output": str(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
