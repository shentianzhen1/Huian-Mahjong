"""Eligibility gate for cross-match real-public opponent meld probes."""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from workspace.vision.public_identity_labels import (
    approved_labels,
    load_public_identity_manifest,
)
from workspace.vision.public_identity_shadow_v0_2 import load_development_sources

QUERIES = {
    "m123": {
        "review_id": "opp_meld_14_m123",
        "query_match_group": "reviewed_recording_14",
        "expected_tiles": ("M1", "M2", "M3"),
    },
    "s456": {
        "review_id": "opp_meld_0926_hand1_s456",
        "query_match_group": "reviewed_match_2026_09_26_first_hand",
        "expected_tiles": ("S4", "S5", "S6"),
    },
}


def run(repository_root: str | Path = ".") -> dict[str, Any]:
    root = Path(repository_root).resolve()
    manifest = load_public_identity_manifest(
        root / "references/vision/2026-09-22/public_identity_labels_v0_1.json"
    )
    sources = load_development_sources(
        root / "references/vision/2026-09-24/public_identity_source_groups.development.json"
    )
    labels = [
        row for row in approved_labels(manifest)
        if row.region == "public_meld"
    ]

    queries: dict[str, Any] = {}
    for name, spec in QUERIES.items():
        coverage: dict[str, Any] = {}
        all_available = True
        for tile in spec["expected_tiles"]:
            groups: dict[str, int] = defaultdict(int)
            for row in labels:
                if row.tile_id != tile:
                    continue
                source = sources.get(row.source_session)
                if source is None or source.source_sha256 != row.source_sha256:
                    continue
                if source.match_group == spec["query_match_group"]:
                    continue
                groups[source.match_group] += 1
            count = sum(groups.values())
            if count == 0:
                all_available = False
            coverage[tile] = {
                "cross_match_real_face_count": count,
                "independent_match_group_count": len(groups),
                "labels_by_match_group": dict(sorted(groups.items())),
            }
        queries[name] = {
            **spec,
            "expected_tiles": list(spec["expected_tiles"]),
            "cross_match_real_reference_coverage": coverage,
            "real_public_probe_eligible": all_available,
            "status": (
                "ELIGIBLE_DEVELOPMENT_ONLY"
                if all_available
                else "BLOCKED_MISSING_CROSS_MATCH_REAL_PUBLIC_REFERENCE"
            ),
        }

    return {
        "schema_version": "opponent_meld_real_public_eligibility_v0_1",
        "date": "2026-10-01",
        "issue": 69,
        "queries": queries,
        "same_match_reference_forbidden": True,
        "evidence_role": "development_selection_only",
        "changes_runtime_behavior": False,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = run()
    Path(args.output).write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["queries"], sort_keys=True))


if __name__ == "__main__":
    main()
