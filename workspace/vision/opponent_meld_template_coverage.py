"""Development-only lineage coverage audit for opponent meld identity."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from workspace.vision.concealed_template_match_lineage import (
    load_concealed_template_lineage,
    qualify_concealed_template_labels,
)
from workspace.vision.tiles_v0_1.labels import approved_labels

QUERY_MATCH_GROUP = "reviewed_match_2026_09_26_first_hand"
TARGETS = ("S4", "S5", "S6")


def run(repository_root: str | Path = ".") -> dict:
    root = Path(repository_root).resolve()
    dataset = root / "dataset/tiles_runtime_v0_2"
    lineage_path = root / "references/vision/2026-10-01/concealed_template_match_lineage.development.json"
    lineage = load_concealed_template_lineage(lineage_path)
    candidates = [
        row for row in approved_labels(dataset)
        if row.get("region") == "hand_region" and not row.get("gold_skin_only")
    ]
    qualified, info = qualify_concealed_template_labels(
        candidates, lineage, query_match_group=QUERY_MATCH_GROUP
    )
    counts = {tile: defaultdict(int) for tile in TARGETS}
    examples = {tile: [] for tile in TARGETS}
    for row in qualified:
        tile = row.get("tile_id")
        if tile not in counts:
            continue
        group = str(row.get("_original_match_group") or "UNKNOWN")
        counts[tile][group] += 1
        examples[tile].append({
            "match_group": group,
            "source_session": row.get("source_session"),
            "source_frame": row.get("source_frame"),
            "image": row.get("image"),
        })
    per_tile = {}
    for tile in TARGETS:
        per_tile[tile] = {
            "qualified_label_count": sum(counts[tile].values()),
            "independent_match_group_count": len(counts[tile]),
            "labels_by_match_group": dict(sorted(counts[tile].items())),
            "examples": examples[tile],
        }
    return {
        "schema_version": "opponent_meld_template_coverage_v0_1",
        "date": "2026-10-01",
        "issue": 69,
        "review_id": "opp_meld_0926_hand1_s456",
        "query_match_group_excluded": QUERY_MATCH_GROUP,
        "target_tiles": list(TARGETS),
        "per_tile": per_tile,
        "lineage_qualification": info,
        "evidence_role": "development_measurement_only",
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
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["per_tile"], sort_keys=True))


if __name__ == "__main__":
    main()
