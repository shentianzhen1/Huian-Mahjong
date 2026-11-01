"""Scan existing reviewed local assets for current concealed support gaps.

Scan-only: candidate crops and reports stay below Runtime's ignored work tree.
Stored sessions select recovery priorities; they never establish independent
original matches or authorize candidate promotion.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from workspace.vision.tiles_v0_1.labels import approved_labels
from .legacy_reviewed_recovery import STANDARD_CLASSES, scan_legacy_class


def scan_legacy_support_gaps(
    legacy_root: str | Path,
    runtime_root: str | Path,
    *,
    tile_ids: list[str] | None = None,
) -> dict:
    runtime = Path(runtime_root)
    legacy = Path(legacy_root)
    if not (runtime / "labels.jsonl").is_file():
        raise FileNotFoundError("Runtime labels.jsonl is required to select current gaps")
    sessions = {tile: set() for tile in STANDARD_CLASSES}
    for row in approved_labels(runtime):
        tile = row.get("tile_id")
        if (
            tile in sessions
            and row.get("region") in {"hand_region", "draw_region", "draw_visual"}
            and not row.get("gold_skin_only")
        ):
            session = row.get("source_session") or row.get("source_id") or "unknown"
            sessions[tile].add(str(session))
    targets = sorted(set(tile_ids) if tile_ids is not None else {
        tile for tile, values in sessions.items() if len(values) < 2
    })
    if not set(targets) <= STANDARD_CLASSES:
        raise ValueError("target classes must be standard tile IDs")

    # approved_labels prefers labels.jsonl when present, matching the single-
    # class recovery tool. Missing data must not be reported as zero candidates.
    available = (legacy / "labels.jsonl").is_file() or (
        legacy / "labels" / "tiles.jsonl"
    ).is_file()
    legacy_labels = approved_labels(legacy) if available else []
    items = []
    for tile in targets:
        item = {
            "tile_id": tile,
            "current_stored_session_count": len(sessions[tile]),
            "current_stored_sessions": sorted(sessions[tile]),
            "candidate_count": None,
            "concealed_candidate_count": None,
            "skipped_count": None,
            "status": "LEGACY_LABELS_UNAVAILABLE",
        }
        if available:
            plan = scan_legacy_class(legacy, runtime, tile_id=tile)
            concealed = sum(
                candidate["region"] in {"hand_region", "draw_visual"}
                for candidate in plan["candidates"]
            )
            item.update(
                candidate_count=plan["candidate_count"],
                concealed_candidate_count=concealed,
                skipped_count=plan["skipped_count"],
                plan=f"{tile}/plan.json",
                status=("CONCEALED_CANDIDATES_REQUIRE_REVIEW" if concealed else
                        "NO_USABLE_CONCEALED_CANDIDATES"),
            )
        items.append(item)
    report = {
        "schema_version": "legacy_reviewed_support_gap_scan_v0_1",
        "local_only": True,
        "scan_only": True,
        "legacy_labels_available": available,
        "legacy_approved_label_count": len(legacy_labels) if available else None,
        "target_classes": targets,
        "items": items,
        "stored_sessions_prove_original_match_independence": False,
        "same_match_clips_must_share_one_logical_session": True,
        "candidate_labels_are_unapproved": True,
        "missing_local_data_proves_assets_lost": False,
        "formal_promotion_evidence": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }
    output = runtime / "work" / "legacy_reviewed_recovery" / "batch_plan.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-dataset", default="dataset/tiles_v0_1")
    parser.add_argument("--runtime-dataset", default="dataset/tiles_runtime_v0_2")
    parser.add_argument("--classes", nargs="+")
    args = parser.parse_args()
    report = scan_legacy_support_gaps(
        args.legacy_dataset, args.runtime_dataset, tile_ids=args.classes,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
