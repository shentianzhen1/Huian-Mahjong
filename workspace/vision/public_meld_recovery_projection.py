"""Project public-meld class coverage if reviewed private recovery succeeds.

This is a diagnostic what-if tool. It does not approve recovered pixels, mutate
identity labels, or change Runtime. A queued recovery match group is added only
for projection; actual template eligibility still requires exact source SHA,
frame lineage, and private pixel comparison.
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


def project_public_meld_recovery_coverage(
    *,
    manifest_path: str | Path,
    registry_path: str | Path,
    recovery_queue_path: str | Path,
) -> dict[str, Any]:
    manifest = load_public_identity_manifest(manifest_path)
    sources = load_development_sources(registry_path)
    queue = load_private_recovery_queue(recovery_queue_path)

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

    before = {tile: set(groups) for tile, groups in groups_by_class.items()}
    projected = {tile: set(groups) for tile, groups in groups_by_class.items()}
    recovery_tiles: dict[str, set[str]] = defaultdict(set)

    for item in queue.items:
        for tile_id in item.expected_tiles:
            recovery_tiles[tile_id].add(item.recovery_id)
            projected.setdefault(tile_id, set()).add(queue.match_group)

    all_tiles = sorted(set(before) | set(projected))
    rows = []
    newly_new_match_supported = []
    newly_introduced_classes = []
    for tile_id in all_tiles:
        before_count = len(before.get(tile_id, set()))
        after_count = len(projected.get(tile_id, set()))
        before_ready = before_count >= 2
        after_ready = after_count >= 2
        if not before_ready and after_ready:
            newly_new_match_supported.append(tile_id)
        if before_count == 0 and after_count > 0:
            newly_introduced_classes.append(tile_id)
        rows.append(
            {
                "tile_id": tile_id,
                "before_independent_match_group_count": before_count,
                "projected_independent_match_group_count": after_count,
                "before_new_match_query_support": before_ready,
                "projected_new_match_query_support": after_ready,
                "recovery_ids": sorted(recovery_tiles.get(tile_id, set())),
            }
        )

    return {
        "schema_version": "public_meld_recovery_coverage_projection_v0_1",
        "match_group_added_by_recovery": queue.match_group,
        "queued_recovery_item_count": len(queue.items),
        "newly_new_match_query_supported_classes": newly_new_match_supported,
        "newly_new_match_query_supported_class_count": len(
            newly_new_match_supported
        ),
        "newly_introduced_classes": newly_introduced_classes,
        "classes": rows,
        "projection_assumes_all_queued_recoveries_qualify": True,
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
    parser.add_argument("--output")
    args = parser.parse_args()

    report = project_public_meld_recovery_coverage(
        manifest_path=args.manifest,
        registry_path=args.registry,
        recovery_queue_path=args.queue,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
