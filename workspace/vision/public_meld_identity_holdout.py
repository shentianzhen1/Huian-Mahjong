"""Blind evaluator for the frozen public-meld identity candidate.

This module is intentionally offline and development-only. It evaluates a
future source-disjoint query packet with the already-frozen candidate; it never
changes candidate parameters, the public template bank, Runtime, Hint, or
Executor.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any

from workspace.vision.public_identity_labels import (
    load_public_identity_manifest,
)
from workspace.vision.public_identity_shadow_v0_2 import (
    ShadowBank,
    _feature,
    build_shadow_bank,
    load_development_sources,
    propose_shadow_identity,
)
from workspace.vision.public_meld_identity_candidate import (
    assert_holdout_is_eligible_for_frozen_candidate,
    load_public_meld_identity_candidate,
)
from workspace.vision.public_meld_identity_normalization import (
    normalize_public_meld_identity_query_face,
)


QUERY_SCHEMA = "public_identity_query_images_v0_1"


def _load_holdout_packet(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != QUERY_SCHEMA:
        raise ValueError("unsupported public identity query packet")
    if payload.get("development_only") is not True:
        raise ValueError("holdout packet must remain development_only")
    if payload.get("query_only") is not True:
        raise ValueError("holdout packet must be query_only")
    if payload.get("excluded_from_formal_promotion") is not True:
        raise ValueError("holdout packet must stay excluded from formal promotion")
    if payload.get("training_template_eligible") is not False:
        raise ValueError("holdout query pixels must not be template eligible")
    for key in ("source_session", "source_sha256", "match_group"):
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise ValueError(f"holdout packet requires {key}")
    queries = payload.get("queries")
    if not isinstance(queries, list) or not queries:
        raise ValueError("holdout packet requires queries")
    for row in queries:
        if not isinstance(row, dict):
            raise ValueError("holdout query row must be an object")
        if row.get("region") != "public_meld":
            raise ValueError("frozen candidate accepts public_meld queries only")
        for key in ("query_id", "expected_tile", "image_path", "image_sha256"):
            if not isinstance(row.get(key), str) or not row[key]:
                raise ValueError(f"holdout query requires {key}")
    return payload


def _rank_image(
    bank: ShadowBank,
    image: Any,
    *,
    source_session: str,
    source_sha256: str,
) -> dict[str, Any]:
    """Return source-disjoint top-1 diagnostics without changing strict gates."""
    import numpy as np

    source = bank.sources.get(source_session)
    if source is None or source.source_sha256 != source_sha256:
        raise ValueError("query source session/SHA not in locked registry")
    query = _feature(image)
    if query is None:
        return {
            "top1_tile": None,
            "top1_score": None,
            "runner_up_tile": None,
            "runner_up_score": None,
            "margin": None,
            "eligible_class_count": 0,
        }

    best_by_class_and_group: dict[str, dict[str, float]] = defaultdict(dict)
    for template in bank.templates:
        if (
            template.region != "public_meld"
            or template.match_group == source.match_group
            or template.source_sha256 == source_sha256
        ):
            continue
        score = float(np.dot(query, template.feature))
        old = best_by_class_and_group[template.tile_id].get(
            template.match_group, -2.0
        )
        best_by_class_and_group[template.tile_id][template.match_group] = max(
            old, score
        )

    eligible = sorted(
        (
            (tile_id, sorted(group_scores.values(), reverse=True)[1])
            for tile_id, group_scores in best_by_class_and_group.items()
            if len(group_scores) >= 2
        ),
        key=lambda row: (-row[1], row[0]),
    )
    if not eligible:
        return {
            "top1_tile": None,
            "top1_score": None,
            "runner_up_tile": None,
            "runner_up_score": None,
            "margin": None,
            "eligible_class_count": 0,
        }

    top_tile, top_score = eligible[0]
    runner_tile = eligible[1][0] if len(eligible) > 1 else None
    runner_score = eligible[1][1] if len(eligible) > 1 else None
    margin = top_score - runner_score if runner_score is not None else None
    return {
        "top1_tile": top_tile,
        "top1_score": round(float(top_score), 6),
        "runner_up_tile": runner_tile,
        "runner_up_score": (
            round(float(runner_score), 6) if runner_score is not None else None
        ),
        "margin": round(float(margin), 6) if margin is not None else None,
        "eligible_class_count": len(eligible),
    }


def evaluate_frozen_public_meld_holdout(
    repository_root: str | Path,
    query_packet_path: str | Path,
    *,
    candidate_path: str | Path = (
        "references/vision/2026-10-01/"
        "public_meld_identity_candidate_v0_1.json"
    ),
    identity_manifest_path: str | Path = (
        "references/vision/2026-09-22/public_identity_labels_v0_1.json"
    ),
    registry_path: str | Path = (
        "references/vision/2026-09-24/"
        "public_identity_source_groups.development.json"
    ),
    minimum_score: float = 0.93,
    minimum_margin: float = 0.075,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    packet = _load_holdout_packet(root / query_packet_path)
    candidate = load_public_meld_identity_candidate(root / candidate_path)
    sources = load_development_sources(root / registry_path)

    source = sources.get(packet["source_session"])
    if source is None:
        raise ValueError("holdout source session is not in locked registry")
    if source.source_sha256 != packet["source_sha256"]:
        raise ValueError("holdout source SHA conflicts with locked registry")
    if source.match_group != packet["match_group"]:
        raise ValueError("holdout match group conflicts with locked registry")

    assert_holdout_is_eligible_for_frozen_candidate(
        candidate,
        holdout_match_group=source.match_group,
        candidate_changed_after_freeze=False,
        query_pixels_used_as_templates=False,
    )

    bank = build_shadow_bank(
        load_public_identity_manifest(root / identity_manifest_path),
        root,
        root / registry_path,
    )

    from PIL import Image

    rows: list[dict[str, Any]] = []
    for query in packet["queries"]:
        image_path = (root / query["image_path"]).resolve()
        if root not in image_path.parents:
            raise ValueError("holdout image escapes repository root")
        if not image_path.is_file():
            raise ValueError(f"missing holdout image: {query['query_id']}")
        digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
        if digest != query["image_sha256"]:
            raise ValueError(f"holdout image SHA mismatch: {query['query_id']}")

        with Image.open(image_path) as original:
            raw = original.convert("RGB")
        normalized = normalize_public_meld_identity_query_face(
            raw,
            inset_ratio=candidate.inset_ratio,
        )
        ranking = _rank_image(
            bank,
            normalized.image,
            source_session=packet["source_session"],
            source_sha256=packet["source_sha256"],
        )
        strict = propose_shadow_identity(
            bank,
            normalized.image,
            region="public_meld",
            source_session=packet["source_session"],
            source_sha256=packet["source_sha256"],
            minimum_score=minimum_score,
            minimum_margin=minimum_margin,
        )
        expected = query["expected_tile"]
        rows.append({
            "query_id": query["query_id"],
            "expected_tile": expected,
            **ranking,
            "top1_correct": ranking["top1_tile"] == expected,
            "strict_gate_candidate": strict.get("read_only_runtime_candidate"),
            "strict_gate_score": strict.get("score"),
            "strict_gate_margin": strict.get("margin"),
            "strict_gate_accepted": strict.get("read_only_runtime_candidate") is not None,
            "strict_gate_correct": strict.get("read_only_runtime_candidate") == expected,
            "strict_gate_reason": strict.get("reason"),
        })

    top1_correct = sum(bool(row["top1_correct"]) for row in rows)
    accepted = [row for row in rows if row["strict_gate_accepted"]]
    accepted_correct = sum(bool(row["strict_gate_correct"]) for row in accepted)

    return {
        "schema_version": "public_meld_identity_holdout_eval_v0_1",
        "candidate_id": candidate.candidate_id,
        "candidate_inset_ratio": candidate.inset_ratio,
        "candidate_changed_after_freeze": False,
        "holdout_match_group": packet["match_group"],
        "query_count": len(rows),
        "top1_correct_count": top1_correct,
        "top1_accuracy": round(top1_correct / len(rows), 6) if rows else None,
        "strict_gate_accepted_count": len(accepted),
        "strict_gate_accepted_accuracy": (
            round(accepted_correct / len(accepted), 6) if accepted else None
        ),
        "queries": rows,
        "development_only": True,
        "source_disjoint_holdout": True,
        "changes_runtime_behavior": False,
        "runtime_promotion_decision": "NOT_DECIDED",
        "formal_promotion_evidence": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--queries", required=True)
    parser.add_argument("--candidate", default=(
        "references/vision/2026-10-01/"
        "public_meld_identity_candidate_v0_1.json"
    ))
    parser.add_argument("--manifest", default=(
        "references/vision/2026-09-22/public_identity_labels_v0_1.json"
    ))
    parser.add_argument("--registry", default=(
        "references/vision/2026-09-24/"
        "public_identity_source_groups.development.json"
    ))
    parser.add_argument("--minimum-score", type=float, default=0.93)
    parser.add_argument("--minimum-margin", type=float, default=0.075)
    args = parser.parse_args()

    report = evaluate_frozen_public_meld_holdout(
        args.repository_root,
        args.queries,
        candidate_path=args.candidate,
        identity_manifest_path=args.manifest,
        registry_path=args.registry,
        minimum_score=args.minimum_score,
        minimum_margin=args.minimum_margin,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
