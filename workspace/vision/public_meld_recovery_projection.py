"""Project public-meld coverage from queued and source-verified recoveries.

Diagnostic only. Queued projection answers "what if every queued private
recovery later qualifies". Source-verified projection is narrower: it includes
only recovery items whose currently accessible raw bytes exactly match the
repository source SHA. Neither projection approves pixels or templates.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from typing import Any

from workspace.vision.public_identity_labels import (
    approved_labels,
    load_public_identity_manifest,
)
from workspace.vision.public_identity_shadow_v0_2 import (
    load_development_sources,
)
from workspace.vision.public_meld_private_recovery_queue import (
    load_private_recovery_queue,
)
from workspace.vision.public_meld_private_recovery_source_check import (
    BLOCKED_SOURCE_SHA_MISMATCH,
    SOURCE_SHA_VERIFIED,
    load_recovery_source_checks,
)


def project_public_meld_recovery_coverage(
    *,
    manifest_path: str | Path,
    registry_path: str | Path,
    recovery_queue_path: str | Path,
    source_check_path: str | Path,
) -> dict[str, Any]:
    manifest = load_public_identity_manifest(manifest_path)
    sources = load_development_sources(registry_path)
    queue = load_private_recovery_queue(recovery_queue_path)
    checks = load_recovery_source_checks(source_check_path)

    groups_by_class: dict[str, set[str]] = defaultdict(set)
    for label in approved_labels(manifest):
        if label.region != "public_meld":
            continue
        source = sources.get(label.source_session)
        if source is None:
            raise ValueError(
                f"public_meld label source not registered: {label.source_session}"
            )
        if source.source_sha256 != label.source_sha256:
            raise ValueError(
                f"public_meld label source SHA mismatch: {label.label_id}"
            )
        groups_by_class[label.tile_id].add(source.match_group)

    queue_ids = {item.recovery_id for item in queue.items}
    if set(checks) != queue_ids:
        raise ValueError("source-check IDs must exactly match recovery queue IDs")

    before = {tile: set(groups) for tile, groups in groups_by_class.items()}
    all_queued = {tile: set(groups) for tile, groups in groups_by_class.items()}
    source_verified = {
        tile: set(groups) for tile, groups in groups_by_class.items()
    }
    recovery_tiles: dict[str, set[str]] = defaultdict(set)
    verified_recovery_ids: list[str] = []
    blocked_recovery_ids: list[str] = []

    for item in queue.items:
        check = checks[item.recovery_id]
        if check.expected_source_sha256 != item.source_sha256_from_repository_evidence:
            raise ValueError(
                f"source-check expected SHA conflicts with queue: {item.recovery_id}"
            )
        for tile_id in item.expected_tiles:
            recovery_tiles[tile_id].add(item.recovery_id)
            all_queued.setdefault(tile_id, set()).add(queue.match_group)

        if check.status == SOURCE_SHA_VERIFIED:
            verified_recovery_ids.append(item.recovery_id)
            for tile_id in item.expected_tiles:
                source_verified.setdefault(tile_id, set()).add(queue.match_group)
        elif check.status == BLOCKED_SOURCE_SHA_MISMATCH:
            blocked_recovery_ids.append(item.recovery_id)
        else:
            raise ValueError("unsupported source-check status")

    all_tiles = sorted(set(before) | set(all_queued) | set(source_verified))
    rows = []
    all_new_ready = []
    verified_new_ready = []
    all_new_classes = []
    verified_new_classes = []

    for tile_id in all_tiles:
        before_count = len(before.get(tile_id, set()))
        queued_count = len(all_queued.get(tile_id, set()))
        verified_count = len(source_verified.get(tile_id, set()))
        before_ready = before_count >= 2
        queued_ready = queued_count >= 2
        verified_ready = verified_count >= 2

        if not before_ready and queued_ready:
            all_new_ready.append(tile_id)
        if not before_ready and verified_ready:
            verified_new_ready.append(tile_id)
        if before_count == 0 and queued_count > 0:
            all_new_classes.append(tile_id)
        if before_count == 0 and verified_count > 0:
            verified_new_classes.append(tile_id)

        rows.append(
            {
                "tile_id": tile_id,
                "before_independent_match_group_count": before_count,
                "all_queued_projected_independent_match_group_count": queued_count,
                "source_verified_projected_independent_match_group_count": (
                    verified_count
                ),
                "before_new_match_query_support": before_ready,
                "all_queued_projected_new_match_query_support": queued_ready,
                "source_verified_projected_new_match_query_support": (
                    verified_ready
                ),
                "recovery_ids": sorted(recovery_tiles.get(tile_id, set())),
            }
        )

    return {
        "schema_version": "public_meld_recovery_coverage_projection_v0_2",
        "match_group_added_by_recovery": queue.match_group,
        "queued_recovery_item_count": len(queue.items),
        "source_verified_recovery_ids": sorted(verified_recovery_ids),
        "blocked_recovery_ids": sorted(blocked_recovery_ids),
        "all_queued_newly_new_match_query_supported_classes": all_new_ready,
        "source_verified_newly_new_match_query_supported_classes": (
            verified_new_ready
        ),
        "all_queued_newly_introduced_classes": all_new_classes,
        "source_verified_newly_introduced_classes": verified_new_classes,
        "classes": rows,
        "all_queued_projection_assumes_later_qualification": True,
        "source_verified_projection_is_not_template_eligibility": True,
        "actual_template_eligibility_still_requires": [
            "exact_source_sha_match",
            "frame_lineage_verification",
            "private_review_packet_pixel_match",
        ],
        "same_match_multiple_hands_count_once": True,
        "changes_runtime_behavior": False,
        "formal_promotion_evidence": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        default="references/vision/2026-09-22/public_identity_labels_v0_1.json",
    )
    parser.add_argument(
        "--registry",
        default=(
            "references/vision/2026-09-24/"
            "public_identity_source_groups.development.json"
        ),
    )
    parser.add_argument(
        "--queue",
        default=(
            "references/vision/2026-10-01/"
            "public_meld_private_recovery_queue_v0_1.json"
        ),
    )
    parser.add_argument(
        "--source-check",
        default=(
            "references/vision/2026-10-01/"
            "public_meld_private_recovery_source_check_v0_1.json"
        ),
    )
    parser.add_argument("--output")
    args = parser.parse_args()

    report = project_public_meld_recovery_coverage(
        manifest_path=args.manifest,
        registry_path=args.registry,
        recovery_queue_path=args.queue,
        source_check_path=args.source_check,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
