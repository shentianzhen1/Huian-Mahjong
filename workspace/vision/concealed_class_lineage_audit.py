"""Audit concealed identity support by reviewed original match.

Template count and source-session count are not independence evidence. This
helper summarizes each standard concealed tile class by exact source SHA and by
reviewed ``original_match_group`` so weak classes can be found before classifier
A/B or Runtime promotion. It is development-only and changes no Runtime logic.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from typing import Any, Iterable

from workspace.vision.concealed_template_match_lineage import (
    ConcealedTemplateSource,
    load_concealed_template_lineage,
)


DEFAULT_DATASET = Path("dataset/tiles_runtime_v0_2")
DEFAULT_LINEAGE = Path(
    "references/vision/2026-10-01/"
    "concealed_template_match_lineage.development.json"
)
STANDARD_CLASSES = tuple(
    [f"M{i}" for i in range(1, 10)]
    + [f"P{i}" for i in range(1, 10)]
    + [f"S{i}" for i in range(1, 10)]
    + ["E", "SOUTH", "W", "N", "R", "G", "B"]
)


def _canonical_region(region: object) -> object:
    return "draw_visual" if region == "draw_region" else region


def load_labels(dataset_root: str | Path) -> list[dict[str, Any]]:
    path = Path(dataset_root) / "labels.jsonl"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def audit_class_lineage(
    labels: Iterable[dict[str, Any]],
    lineage_by_sha: dict[str, ConcealedTemplateSource],
) -> dict[str, Any]:
    by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in labels:
        if not (row.get("approved") is True or row.get("status") == "approved"):
            continue
        if row.get("gold_skin_only"):
            continue
        if _canonical_region(row.get("region")) not in {"hand_region", "draw_visual"}:
            continue
        tile = row.get("tile_id")
        sha = row.get("sha256")
        if tile not in STANDARD_CLASSES or not isinstance(sha, str):
            continue
        by_class[str(tile)].append(row)

    class_rows = []
    for tile in STANDARD_CLASSES:
        rows = by_class.get(tile, [])
        source_shas = sorted({str(row["sha256"]) for row in rows})
        sessions = sorted(
            {
                str(row["source_session"])
                for row in rows
                if isinstance(row.get("source_session"), str)
            }
        )
        groups = sorted(
            {
                lineage_by_sha[sha].match_group
                for sha in source_shas
                if sha in lineage_by_sha
            }
        )
        unresolved = sorted(sha for sha in source_shas if sha not in lineage_by_sha)
        class_rows.append(
            {
                "tile_id": tile,
                "ordinary_template_count": len(rows),
                "distinct_source_sha_count": len(source_shas),
                "distinct_source_session_count": len(sessions),
                "reviewed_original_match_group_count": len(groups),
                "reviewed_original_match_groups": groups,
                "unresolved_source_sha_count": len(unresolved),
                "unresolved_source_shas": unresolved,
                "source_session_used_as_independence_signal": False,
            }
        )

    present = [row for row in class_rows if row["ordinary_template_count"] > 0]
    reviewed = [
        row for row in class_rows if row["reviewed_original_match_group_count"] > 0
    ]
    return {
        "schema_version": "concealed_class_lineage_audit_v0_1",
        "development_only": True,
        "lineage_key": "exact_source_sha256",
        "standard_class_count": len(STANDARD_CLASSES),
        "classes_with_any_template_count": len(present),
        "classes_with_reviewed_lineage_count": len(reviewed),
        "classes_without_any_template": [
            row["tile_id"] for row in class_rows if row["ordinary_template_count"] == 0
        ],
        "classes_without_reviewed_lineage": [
            row["tile_id"]
            for row in class_rows
            if row["reviewed_original_match_group_count"] == 0
        ],
        "classes_with_fewer_than_two_reviewed_matches": [
            row["tile_id"]
            for row in class_rows
            if row["reviewed_original_match_group_count"] < 2
        ],
        "classes": class_rows,
        "source_session_used_as_independence_signal": False,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--lineage", default=str(DEFAULT_LINEAGE))
    parser.add_argument("--output")
    args = parser.parse_args()
    report = audit_class_lineage(
        load_labels(args.dataset),
        load_concealed_template_lineage(args.lineage),
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
