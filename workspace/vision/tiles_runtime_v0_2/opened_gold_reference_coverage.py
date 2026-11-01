"""Audit opened-Gold identity evidence without changing Runtime behavior.

Runtime Vision currently builds its Gold identity bank by projecting every
approved tile crop through the Gold normalization path, while its safety gate
uses ``source_session`` multiplicity as a historical cross-session signal.
Storage/session identifiers are not proof that two templates come from
independent original matches.  This offline audit compares the legacy signal
with the reviewed exact-source-SHA -> original-match lineage registry and also
reports the much smaller set of direct ``gold_region`` / real Gold-skin
references.

The report is development evidence only.  It does not alter Runtime, Hint
Alpha, the frozen 0.82 threshold, or any template labels.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any, Iterable

from workspace.vision.concealed_template_match_lineage import (
    ConcealedTemplateSource,
    load_concealed_template_lineage,
    verify_lineage_evidence_paths,
)
from workspace.vision.tiles_v0_1.labels import approved_labels


GOLD_IDENTITY_SOURCE_REGIONS = frozenset(
    {"hand_region", "draw_region", "draw_visual", "gold_region"}
)


def _session_key(row: dict[str, Any]) -> str:
    """Mirror Runtime's historical source-session fallback exactly."""
    return row.get("source_session") or row.get("source_id") or "unknown"


def _match_group(
    row: dict[str, Any],
    lineage_by_sha: dict[str, ConcealedTemplateSource],
) -> str | None:
    source = lineage_by_sha.get(row.get("sha256"))
    return None if source is None else source.match_group


def _reference_summary(
    rows: Iterable[dict[str, Any]],
    lineage_by_sha: dict[str, ConcealedTemplateSource],
) -> dict[str, Any]:
    rows = list(rows)
    groups = {
        group
        for row in rows
        if (group := _match_group(row, lineage_by_sha)) is not None
    }
    classes = {row["tile_id"] for row in rows}
    qualified = sum(
        _match_group(row, lineage_by_sha) is not None for row in rows
    )
    return {
        "label_count": len(rows),
        "class_count": len(classes),
        "classes": sorted(classes),
        "reviewed_lineage_label_count": qualified,
        "unknown_lineage_label_count": len(rows) - qualified,
        "reviewed_original_match_group_count": len(groups),
        "reviewed_original_match_groups": sorted(groups),
    }


def audit_opened_gold_reference_coverage(
    labels: Iterable[dict[str, Any]],
    lineage_by_sha: dict[str, ConcealedTemplateSource],
) -> dict[str, Any]:
    """Compare legacy session support with reviewed original-match support."""
    approved = [row for row in labels if row.get("approved")]
    projected = [
        row
        for row in approved
        if row.get("region") in GOLD_IDENTITY_SOURCE_REGIONS
        or row.get("gold_skin_only")
    ]

    sessions_by_tile: dict[str, set[str]] = defaultdict(set)
    groups_by_tile: dict[str, set[str]] = defaultdict(set)
    unknown_lineage_by_tile: Counter[str] = Counter()
    label_count_by_tile: Counter[str] = Counter()
    region_count = Counter()

    for row in projected:
        tile_id = row["tile_id"]
        label_count_by_tile[tile_id] += 1
        sessions_by_tile[tile_id].add(_session_key(row))
        region_count[row.get("region") or "unknown"] += 1
        group = _match_group(row, lineage_by_sha)
        if group is None:
            unknown_lineage_by_tile[tile_id] += 1
        else:
            groups_by_tile[tile_id].add(group)

    legacy_cross_session = {
        tile_id
        for tile_id, sessions in sessions_by_tile.items()
        if len(sessions) >= 2
    }
    reviewed_cross_match = {
        tile_id
        for tile_id, groups in groups_by_tile.items()
        if len(groups) >= 2
    }
    legacy_only = legacy_cross_session - reviewed_cross_match

    legacy_only_details = []
    for tile_id in sorted(legacy_only):
        legacy_only_details.append({
            "tile_id": tile_id,
            "projected_label_count": label_count_by_tile[tile_id],
            "legacy_source_session_count": len(sessions_by_tile[tile_id]),
            "reviewed_original_match_group_count": len(groups_by_tile[tile_id]),
            "reviewed_original_match_groups": sorted(groups_by_tile[tile_id]),
            "unknown_lineage_label_count": unknown_lineage_by_tile[tile_id],
        })

    direct_gold = [row for row in approved if row.get("region") == "gold_region"]
    real_gold_skin = [row for row in approved if row.get("gold_skin_only")]

    direct_details = []
    for row in direct_gold:
        group = _match_group(row, lineage_by_sha)
        direct_details.append({
            "tile_id": row["tile_id"],
            "source_sha256": row.get("sha256"),
            "source_session": row.get("source_session"),
            "reviewed_original_match_group": group,
            "lineage_status": "REVIEWED" if group is not None else "UNKNOWN",
            "image": row.get("image"),
        })

    gold_skin_details = []
    for row in real_gold_skin:
        group = _match_group(row, lineage_by_sha)
        gold_skin_details.append({
            "tile_id": row["tile_id"],
            "region": row.get("region"),
            "source_sha256": row.get("sha256"),
            "source_session": row.get("source_session"),
            "reviewed_original_match_group": group,
            "lineage_status": "REVIEWED" if group is not None else "UNKNOWN",
            "asset_role": row.get("asset_role"),
            "image": row.get("image"),
        })

    return {
        "schema_version": "opened_gold_reference_coverage_v0_1",
        "status": "DEVELOPMENT_EVIDENCE_AUDIT_NOT_RUNTIME_POLICY",
        "runtime_changed": False,
        "hint_changed": False,
        "executor_changed": False,
        "runtime_identity_threshold_changed": False,
        "source_session_is_independence_signal": False,
        "formal_promotion_evidence": False,
        "approved_label_count": len(approved),
        "projected_gold_identity_bank": {
            **_reference_summary(projected, lineage_by_sha),
            "source_region_counts": dict(sorted(region_count.items())),
            "construction_note": (
                "Matches the current classifier design: every approved hand/draw/gold "
                "reference can be projected through Gold normalization."
            ),
        },
        "direct_gold_region_references": {
            **_reference_summary(direct_gold, lineage_by_sha),
            "references": direct_details,
        },
        "real_gold_skin_evidence": {
            **_reference_summary(real_gold_skin, lineage_by_sha),
            "references": gold_skin_details,
        },
        "independence_comparison": {
            "legacy_runtime_definition": "at_least_two_source_session_or_source_id_values",
            "reviewed_definition": "at_least_two_reviewed_original_match_groups_by_exact_source_sha256",
            "legacy_cross_session_class_count": len(legacy_cross_session),
            "legacy_cross_session_classes": sorted(legacy_cross_session),
            "reviewed_cross_match_class_count": len(reviewed_cross_match),
            "reviewed_cross_match_classes": sorted(reviewed_cross_match),
            "legacy_cross_session_but_not_reviewed_cross_match_class_count": len(legacy_only),
            "legacy_cross_session_but_not_reviewed_cross_match_classes": sorted(legacy_only),
            "legacy_only_details": legacy_only_details,
            "reviewed_cross_match_not_legacy_classes": sorted(
                reviewed_cross_match - legacy_cross_session
            ),
        },
        "finding": (
            "source_session multiplicity overstates independent opened-Gold identity "
            "support whenever multiple storage sessions belong to one reviewed original "
            "match or have UNKNOWN lineage."
        ),
        "safe_for_runtime_policy_change": False,
        "next_step": (
            "Use reviewed original_match_group lineage for any future opened-Gold "
            "promotion audit, and grow a direct reviewed Gold-indicator/Gold-skin bank "
            "before changing Runtime identity acceptance."
        ),
    }


def build_report(
    dataset_root: str | Path,
    lineage_path: str | Path,
    *,
    repository_root: str | Path | None = None,
) -> dict[str, Any]:
    lineage = load_concealed_template_lineage(lineage_path)
    if repository_root is not None:
        issues = verify_lineage_evidence_paths(lineage, repository_root)
        if issues:
            raise ValueError(f"lineage evidence paths failed verification: {issues}")
    return audit_opened_gold_reference_coverage(
        approved_labels(Path(dataset_root)),
        lineage,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--lineage", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = build_report(
        args.dataset,
        args.lineage,
        repository_root=args.repository_root,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    comparison = report["independence_comparison"]
    print(
        "Opened-Gold coverage audit: "
        f"{report['approved_label_count']} labels, "
        f"{comparison['legacy_cross_session_class_count']} legacy cross-session classes, "
        f"{comparison['reviewed_cross_match_class_count']} reviewed cross-match classes; "
        "no Runtime changes"
    )


if __name__ == "__main__":
    main()
