"""Audit direct opened-Gold evidence for independent holdout readiness.

A burst, adjacent frames, or multiple clips from one original match are one
source for independence purposes.  This development-only audit collapses all
reviewed direct opened-Gold evidence by ``original_match_group`` and refuses to
claim an empirical holdout until the same tile class has direct reviewed
appearance evidence from at least two distinct original matches.

This module does not change Runtime, Hint Alpha, AI V0.10, Executor, or the
frozen 0.82 identity threshold.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from typing import Any, Iterable

NO_REVIEWED_DIRECT_REFERENCE = "NO_REVIEWED_DIRECT_REFERENCE"
ONE_REVIEWED_ORIGINAL_MATCH_NO_HOLDOUT = "ONE_REVIEWED_ORIGINAL_MATCH_NO_HOLDOUT"
ELIGIBLE_FOR_LEAVE_ONE_MATCH_OUT = "ELIGIBLE_FOR_LEAVE_ONE_MATCH_OUT"

_REQUIRED_FIELDS = (
    "tile_id",
    "evidence_kind",
    "source_sha256",
    "lineage_status",
    "evidence_path",
    "checkpoint_count",
)


def validate_evidence_entries(
    entries: Iterable[dict[str, Any]],
    *,
    repository_root: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Validate metadata only; pixel data is intentionally not part of this audit."""
    validated: list[dict[str, Any]] = []
    root = Path(repository_root) if repository_root is not None else None
    for index, original in enumerate(entries):
        row = dict(original)
        missing = [field for field in _REQUIRED_FIELDS if field not in row]
        if missing:
            raise ValueError(f"evidence[{index}] missing required fields: {missing}")
        if not row["tile_id"]:
            raise ValueError(f"evidence[{index}] tile_id is empty")
        if row["lineage_status"] not in {"REVIEWED", "UNKNOWN"}:
            raise ValueError(
                f"evidence[{index}] invalid lineage_status: {row['lineage_status']}"
            )
        if row["lineage_status"] == "REVIEWED" and not row.get("original_match_group"):
            raise ValueError(
                f"evidence[{index}] reviewed evidence requires original_match_group"
            )
        checkpoint_count = row["checkpoint_count"]
        if isinstance(checkpoint_count, bool) or not isinstance(checkpoint_count, int):
            raise ValueError(f"evidence[{index}] checkpoint_count must be an integer")
        if checkpoint_count < 1:
            raise ValueError(f"evidence[{index}] checkpoint_count must be >= 1")
        evidence_path = Path(row["evidence_path"])
        if evidence_path.is_absolute() or ".." in evidence_path.parts:
            raise ValueError(f"evidence[{index}] evidence_path must be repository-relative")
        if root is not None and not (root / evidence_path).is_file():
            raise ValueError(
                f"evidence[{index}] evidence_path does not exist: {evidence_path}"
            )
        validated.append(row)
    return validated


def audit_direct_gold_holdout_readiness(
    entries: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Collapse evidence by tile + original match and report holdout readiness."""
    rows = validate_evidence_entries(entries)
    by_tile: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_tile[row["tile_id"]].append(row)

    per_class: dict[str, dict[str, Any]] = {}
    eligible: list[str] = []
    no_holdout: list[str] = []
    no_reviewed: list[str] = []

    for tile_id in sorted(by_tile):
        tile_rows = by_tile[tile_id]
        reviewed_rows = [
            row
            for row in tile_rows
            if row["lineage_status"] == "REVIEWED"
            and row.get("original_match_group")
        ]
        reviewed_groups = sorted(
            {row["original_match_group"] for row in reviewed_rows}
        )
        match_count = len(reviewed_groups)
        if match_count == 0:
            readiness = NO_REVIEWED_DIRECT_REFERENCE
            no_reviewed.append(tile_id)
        elif match_count == 1:
            readiness = ONE_REVIEWED_ORIGINAL_MATCH_NO_HOLDOUT
            no_holdout.append(tile_id)
        else:
            readiness = ELIGIBLE_FOR_LEAVE_ONE_MATCH_OUT
            eligible.append(tile_id)

        per_class[tile_id] = {
            "readiness": readiness,
            "evidence_record_count": len(tile_rows),
            "checkpoint_count": sum(row["checkpoint_count"] for row in tile_rows),
            "reviewed_evidence_record_count": len(reviewed_rows),
            "reviewed_original_match_count": match_count,
            "reviewed_original_match_groups": reviewed_groups,
            "unknown_lineage_evidence_record_count": sum(
                row["lineage_status"] != "REVIEWED" for row in tile_rows
            ),
            "evidence_kinds": sorted({row["evidence_kind"] for row in tile_rows}),
            "source_sha256": sorted({row["source_sha256"] for row in tile_rows}),
            "checkpoint_count_is_independence_count": False,
        }

    reviewed_records = [
        row
        for row in rows
        if row["lineage_status"] == "REVIEWED" and row.get("original_match_group")
    ]
    return {
        "schema_version": "opened_gold_direct_holdout_readiness_v0_1",
        "status": "DEVELOPMENT_HOLDOUT_READINESS_NOT_ACCURACY",
        "runtime_changed": False,
        "hint_changed": False,
        "executor_changed": False,
        "ai_version_changed": False,
        "runtime_identity_threshold_reference": 0.82,
        "runtime_identity_threshold_changed": False,
        "source_session_is_independence_signal": False,
        "adjacent_frames_are_independent_sources": False,
        "same_match_different_clips_are_independent_sources": False,
        "formal_promotion_evidence": False,
        "accuracy_claimed": False,
        "evidence_record_count": len(rows),
        "reviewed_evidence_record_count": len(reviewed_records),
        "unknown_lineage_evidence_record_count": len(rows) - len(reviewed_records),
        "class_count": len(per_class),
        "eligible_for_leave_one_match_out_class_count": len(eligible),
        "eligible_for_leave_one_match_out_classes": eligible,
        "one_reviewed_match_no_holdout_classes": no_holdout,
        "no_reviewed_direct_reference_classes": no_reviewed,
        "per_class": per_class,
        "finding": (
            "Multiple checkpoints from one original match collapse to one independence "
            "unit. A tile class needs direct reviewed opened-Gold evidence from at "
            "least two distinct original_match_group values before leave-one-match-out "
            "evaluation is even eligible."
        ),
        "safe_for_runtime_policy_change": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def build_report(
    manifest_path: str | Path,
    *,
    repository_root: str | Path | None = None,
) -> dict[str, Any]:
    manifest_path = Path(manifest_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "opened_gold_direct_evidence_manifest_v0_1":
        raise ValueError("unsupported direct opened-Gold evidence manifest schema")
    entries = validate_evidence_entries(
        payload.get("evidence", []), repository_root=repository_root
    )
    report = audit_direct_gold_holdout_readiness(entries)
    report["manifest"] = manifest_path.as_posix()
    report["manifest_evidence_authority"] = payload.get("evidence_authority")
    report["raw_or_derived_pixels_in_report"] = False
    report["next_step"] = (
        "Acquire or recover a second reviewed original match containing the same "
        "directly visible opened-Gold tile class before evaluating that class with an "
        "independent holdout. Do not promote repeated frames or same-match clips."
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--repository-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(args.manifest, repository_root=args.repository_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        "Opened-Gold direct holdout readiness: "
        f"{report['class_count']} classes, "
        f"{report['eligible_for_leave_one_match_out_class_count']} holdout-eligible; "
        "no Runtime changes"
    )


if __name__ == "__main__":
    main()
