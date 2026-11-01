"""Build metadata-only recovery queues for concealed-template match lineage.

This tool never guesses match groups from source_session names. Historical
Oct-1 recovery artifacts were built from ``hand_region`` only, so
``build_lineage_recovery_queue`` preserves that default for reproducibility.
Current Runtime Vision pools ``hand_region`` and ``draw_visual`` into the same
concealed identity domain; new audits must use
``build_concealed_identity_lineage_recovery_queue`` so draw-position labels
cannot silently escape original-match lineage review.
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


HAND_ONLY_SOURCE_REGIONS = frozenset({"hand_region"})
CONCEALED_IDENTITY_SOURCE_REGIONS = frozenset({"hand_region", "draw_visual"})


def build_lineage_recovery_queue(
    labels: Iterable[dict[str, Any]],
    lineage_by_sha: dict[str, ConcealedTemplateSource],
    *,
    target_classes: set[str] | None = None,
    source_regions: frozenset[str] = HAND_ONLY_SOURCE_REGIONS,
) -> dict[str, Any]:
    """Build a fail-closed queue for explicitly selected identity regions.

    The default remains hand-only solely so frozen historical artifacts stay
    reproducible. New concealed Runtime audits should call the dedicated
    wrapper below rather than relying on this default.
    """
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in labels:
        if (
            row.get("region") not in source_regions
            or row.get("gold_skin_only")
            or not (
                row.get("status") == "approved"
                or row.get("approved") is True
            )
        ):
            continue
        tile_id = row.get("tile_id")
        sha = row.get("sha256")
        if not isinstance(tile_id, str) or not isinstance(sha, str):
            continue
        if target_classes is not None and tile_id not in target_classes:
            continue
        if sha in lineage_by_sha:
            continue
        grouped[sha].append(row)

    items: list[dict[str, Any]] = []
    for sha, rows in sorted(grouped.items()):
        sessions = sorted(
            {
                str(row.get("source_session"))
                for row in rows
                if row.get("source_session")
            }
        )
        frames = sorted(
            {
                int(row["source_frame"])
                for row in rows
                if isinstance(row.get("source_frame"), int)
            }
        )
        items.append(
            {
                "source_sha256": sha,
                "source_sessions": sessions,
                "tile_classes": sorted(
                    {str(row["tile_id"]) for row in rows}
                ),
                "approved_label_count": len(rows),
                "source_frames": frames,
                "status": "UNKNOWN_ORIGINAL_MATCH",
                "required_evidence": (
                    "reviewed source record tying this exact SHA256 "
                    "to one original recorded match_group"
                ),
                "session_name_is_not_evidence": True,
            }
        )

    return {
        "schema_version": "concealed_template_lineage_recovery_queue_v0_1",
        "development_only": True,
        "match_group_inference_allowed": False,
        "items": items,
        "unresolved_source_count": len(items),
        "unresolved_label_count": sum(
            int(item["approved_label_count"]) for item in items
        ),
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def build_concealed_identity_lineage_recovery_queue(
    labels: Iterable[dict[str, Any]],
    lineage_by_sha: dict[str, ConcealedTemplateSource],
    *,
    target_classes: set[str] | None = None,
) -> dict[str, Any]:
    """Audit every region used by Runtime's pooled concealed identity gate."""
    return build_lineage_recovery_queue(
        labels,
        lineage_by_sha,
        target_classes=target_classes,
        source_regions=CONCEALED_IDENTITY_SOURCE_REGIONS,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--labels",
        default="dataset/tiles_runtime_v0_2/labels.jsonl",
    )
    parser.add_argument(
        "--lineage",
        default=(
            "references/vision/2026-10-01/"
            "concealed_template_match_lineage.development.json"
        ),
    )
    parser.add_argument(
        "--classes",
        nargs="*",
        default=["M1", "M3"],
    )
    parser.add_argument(
        "--concealed-domain",
        action="store_true",
        help="include draw_visual because Runtime pools it with hand_region",
    )
    parser.add_argument("--output")
    args = parser.parse_args()

    labels = [
        json.loads(line)
        for line in Path(args.labels).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    registry = load_concealed_template_lineage(args.lineage)
    builder = (
        build_concealed_identity_lineage_recovery_queue
        if args.concealed_domain
        else build_lineage_recovery_queue
    )
    report = builder(
        labels,
        registry,
        target_classes=set(args.classes) if args.classes else None,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
