"""Audit independent-match coverage for public meld identity labels.

The public_meld identity path is intentionally stricter than ordinary
source-session counting. Multiple clips or hands from the same original match
count as one match group.

This module is read-only and diagnostic:
- it never changes Runtime output;
- it never lowers identity thresholds;
- it never treats same-match duplicate frames as independent evidence.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from typing import Any

from workspace.vision.public_identity_labels import (
    PUBLIC_STANDARD_CLASSES,
    PublicIdentityManifest,
    approved_labels,
    load_public_identity_manifest,
)
from workspace.vision.public_identity_shadow_v0_2 import (
    SourceGroup,
    load_development_sources,
)


def audit_public_meld_identity_coverage(
    manifest: PublicIdentityManifest,
    sources: dict[str, SourceGroup],
) -> dict[str, Any]:
    """Summarize class support by independent original-match group.

    For a query from a *new* match that contributes no training templates, a
    class needs at least two existing independent match groups to satisfy the
    current public shadow gate's winner support rule.

    For strict leave-one-existing-match-out evaluation, at least three total
    match groups are needed so two remain after excluding the query match.
    """
    labels = [
        label
        for label in approved_labels(manifest)
        if label.region == "public_meld"
    ]

    groups_by_class: dict[str, set[str]] = defaultdict(set)
    sessions_by_class: dict[str, set[str]] = defaultdict(set)
    labels_by_class: dict[str, int] = defaultdict(int)
    all_groups: set[str] = set()

    for label in labels:
        source = sources.get(label.source_session)
        if source is None:
            raise ValueError(
                f"public_meld label source not registered: {label.source_session}"
            )
        if source.source_sha256 != label.source_sha256:
            raise ValueError(
                f"public_meld label source SHA mismatch: {label.label_id}"
            )
        labels_by_class[label.tile_id] += 1
        sessions_by_class[label.tile_id].add(label.source_session)
        groups_by_class[label.tile_id].add(source.match_group)
        all_groups.add(source.match_group)

    class_rows: list[dict[str, Any]] = []
    new_match_supported: list[str] = []
    leave_one_out_supported: list[str] = []
    one_group_short: list[str] = []

    for tile_id in sorted(PUBLIC_STANDARD_CLASSES):
        match_group_count = len(groups_by_class[tile_id])
        new_match_ready = match_group_count >= 2
        leave_one_out_ready = match_group_count >= 3
        if new_match_ready:
            new_match_supported.append(tile_id)
        elif match_group_count == 1:
            one_group_short.append(tile_id)
        if leave_one_out_ready:
            leave_one_out_supported.append(tile_id)

        class_rows.append(
            {
                "tile_id": tile_id,
                "approved_label_count": labels_by_class[tile_id],
                "source_session_count": len(sessions_by_class[tile_id]),
                "independent_match_group_count": match_group_count,
                "new_match_query_support": new_match_ready,
                "strict_existing_match_leave_one_out_support": leave_one_out_ready,
                "additional_independent_match_groups_needed_for_new_query": max(
                    0, 2 - match_group_count
                ),
                "additional_independent_match_groups_needed_for_leave_one_out": max(
                    0, 3 - match_group_count
                ),
            }
        )

    return {
        "schema_version": "public_meld_identity_coverage_v0_1",
        "approved_public_meld_labels": len(labels),
        "distinct_public_meld_classes": len(
            [tile for tile, groups in groups_by_class.items() if groups]
        ),
        "distinct_independent_match_groups": len(all_groups),
        "new_match_query_supported_classes": new_match_supported,
        "new_match_query_supported_class_count": len(new_match_supported),
        "strict_existing_match_leave_one_out_supported_classes": (
            leave_one_out_supported
        ),
        "strict_existing_match_leave_one_out_supported_class_count": len(
            leave_one_out_supported
        ),
        "classes_one_independent_match_group_short_for_new_query": one_group_short,
        "classes": class_rows,
        "policy": {
            "same_match_multiple_sessions_count_once": True,
            "new_match_query_required_other_match_groups_per_class": 2,
            "strict_existing_match_leave_one_out_required_total_match_groups": 3,
            "identity_threshold_lowering_allowed": False,
        },
        "diagnostic_only": True,
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
    parser.add_argument("--output")
    args = parser.parse_args()

    manifest = load_public_identity_manifest(args.manifest)
    sources = load_development_sources(args.registry)
    report = audit_public_meld_identity_coverage(manifest, sources)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
