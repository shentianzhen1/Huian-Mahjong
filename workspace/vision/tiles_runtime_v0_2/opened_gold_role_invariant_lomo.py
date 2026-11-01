"""Development-only leave-one-original-match-out audit for Gold role-invariant features.

This audit does not change Runtime. It evaluates the fixed role-invariant
candidate on one deterministic ordinary concealed representative per
(original_match_group, tile_id), while excluding the entire query original
match from the template bank. Same-session and adjacent-frame counts are never
used as independence evidence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from workspace.vision.concealed_template_match_lineage import (
    ConcealedTemplateSource,
    load_concealed_template_lineage,
    verify_lineage_evidence_paths,
)
from workspace.vision.tiles_runtime_v0_2.opened_gold_role_invariant_probe import (
    DEVELOPMENT_GLYPH_MARGIN,
    FROZEN_RUNTIME_THRESHOLD,
    _load_label_crop,
    score_query,
)
from workspace.vision.tiles_v0_1.labels import approved_labels

ORDINARY_CONCEALED_REGIONS = frozenset({"hand_region", "draw_visual"})


def ordinary_concealed_labels(labels: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in labels
        if row.get("region") in ORDINARY_CONCEALED_REGIONS
        and row.get("gold_skin_only") is not True
    ]


def _frame_sort_value(row: dict[str, Any]) -> int:
    value = row.get("source_frame")
    return value if isinstance(value, int) and not isinstance(value, bool) else -1


def representative_labels(
    labels: Iterable[dict[str, Any]],
    lineage: dict[str, ConcealedTemplateSource],
) -> list[dict[str, Any]]:
    """Choose one deterministic label per reviewed original-match + tile class."""
    chosen: dict[tuple[str, str], tuple[tuple[Any, ...], dict[str, Any]]] = {}
    for row in ordinary_concealed_labels(labels):
        sha = row.get("sha256")
        tile = row.get("tile_id")
        source = lineage.get(sha) if isinstance(sha, str) else None
        if source is None or not isinstance(tile, str) or not tile:
            continue
        key = (source.match_group, tile)
        order = (sha, _frame_sort_value(row), str(row.get("image", "")))
        old = chosen.get(key)
        if old is None or order < old[0]:
            chosen[key] = (order, dict(row))
    return [
        item[1]
        for _, item in sorted(chosen.items(), key=lambda pair: pair[0])
    ]


def has_disjoint_truth_reference(
    labels: Iterable[dict[str, Any]],
    lineage: dict[str, ConcealedTemplateSource],
    *,
    query_match_group: str,
    tile_id: str,
) -> bool:
    for row in ordinary_concealed_labels(labels):
        if row.get("tile_id") != tile_id:
            continue
        sha = row.get("sha256")
        source = lineage.get(sha) if isinstance(sha, str) else None
        if source is not None and source.match_group != query_match_group:
            return True
    return False


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scorable = [row for row in rows if row["scorable"]]
    correct = sum(bool(row["correct"]) for row in scorable)
    return {
        "query_count": len(rows),
        "scorable_query_count": len(scorable),
        "correct_query_count": correct,
        "unscorable_query_count": len(rows) - len(scorable),
        "diagnostic_ratio": (correct / len(scorable)) if scorable else None,
    }


def evaluate(
    dataset_root: str | Path,
    lineage_path: str | Path,
    *,
    repository_root: str | Path,
    glyph_margin: float = DEVELOPMENT_GLYPH_MARGIN,
) -> dict[str, Any]:
    dataset = Path(dataset_root)
    lineage = load_concealed_template_lineage(lineage_path)
    issues = verify_lineage_evidence_paths(lineage, repository_root)
    if issues:
        raise ValueError(f"lineage evidence paths failed verification: {issues}")
    all_labels = approved_labels(dataset)
    ordinary = ordinary_concealed_labels(all_labels)
    rows: list[dict[str, Any]] = []

    for query in representative_labels(ordinary, lineage):
        source = lineage[query["sha256"]]
        truth = query["tile_id"]
        scorable = has_disjoint_truth_reference(
            ordinary,
            lineage,
            query_match_group=source.match_group,
            tile_id=truth,
        )
        result = score_query(
            _load_label_crop(dataset, query),
            dataset_root=dataset,
            labels=ordinary,
            lineage=lineage,
            query_match_group=source.match_group,
            glyph_margin=glyph_margin,
        )
        rows.append({
            "query_match_group": source.match_group,
            "truth_tile": truth,
            "query_source_sha256": query["sha256"],
            "query_source_frame": query.get("source_frame"),
            "query_image": query.get("image"),
            "scorable": scorable,
            "candidate_tile": result.get("candidate_tile"),
            "correct": bool(scorable and result.get("candidate_tile") == truth),
            "family": result.get("family"),
            "decision_feature": result.get("decision_feature"),
            "glyph_margin": result.get("glyph_margin"),
            "full_face_winner": result.get("full_face_winner"),
            "glyph_winner": result.get("glyph_winner"),
            "qualified_class_count": result.get("qualified_class_count"),
        })

    summary = summarize(rows)
    failures = [row for row in rows if row["scorable"] and not row["correct"]]
    unscorable = [row for row in rows if not row["scorable"]]
    return {
        "schema_version": "opened_gold_role_invariant_lomo_development_v0_1",
        "status": "REVEALED_DEVELOPMENT_CROSS_MATCH_SEPARABILITY_DIAGNOSTIC_NOT_PROMOTION",
        "scope": "ordinary concealed hand_region/draw_visual templates only; gold_region and gold_skin_only labels excluded",
        "glyph_margin_frozen_from_prior_revealed_probe": float(glyph_margin),
        "representative_policy": "one deterministic approved ordinary concealed label per reviewed original_match_group + tile class; all templates from the query original match excluded",
        "source_session_is_independence_signal": False,
        "adjacent_frames_weighted_as_independent": False,
        "same_match_different_clips_weighted_as_independent": False,
        **summary,
        "formal_accuracy_claim": False,
        "runtime_threshold_reference": FROZEN_RUNTIME_THRESHOLD,
        "runtime_changed": False,
        "hint_changed": False,
        "executor_changed": False,
        "runtime_identity_threshold_changed": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
        "failures": failures,
        "unscorable": unscorable,
        "queries": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--lineage", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--glyph-margin", type=float, default=DEVELOPMENT_GLYPH_MARGIN)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate(
        args.dataset,
        args.lineage,
        repository_root=args.repository_root,
        glyph_margin=args.glyph_margin,
    )
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
