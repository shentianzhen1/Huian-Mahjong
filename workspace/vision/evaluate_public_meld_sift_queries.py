"""Evaluate SIFT public-meld ranking on locked query-only crops."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from workspace.vision.public_identity_labels import load_public_identity_manifest
from workspace.vision.public_meld_identity_sift import (
    build_public_meld_sift_bank,
    rank_public_meld_sift,
)


QUERY_SCHEMA = "public_identity_query_images_v0_1"


def evaluate_public_meld_sift_queries(
    repository_root: str | Path = ".",
    query_path: str | Path = (
        "references/vision/2026-09-30/"
        "first_hand_public_query_features_v0_1.json"
    ),
    manifest_path: str | Path = (
        "references/vision/2026-09-22/public_identity_labels_v0_1.json"
    ),
    registry_path: str | Path = (
        "references/vision/2026-09-24/"
        "public_identity_source_groups.development.json"
    ),
    *,
    minimum_other_match_groups: int = 2,
) -> dict[str, Any]:
    from PIL import Image

    root = Path(repository_root).resolve()
    packet = json.loads((root / query_path).read_text(encoding="utf-8"))
    if (
        not isinstance(packet, dict)
        or packet.get("schema_version") != QUERY_SCHEMA
        or packet.get("development_only") is not True
        or packet.get("query_only") is not True
        or packet.get("training_template_eligible") is not False
    ):
        raise ValueError("expected locked development query-only packet")

    bank = build_public_meld_sift_bank(
        load_public_identity_manifest(root / manifest_path),
        root,
        root / registry_path,
    )

    rows: list[dict[str, Any]] = []
    for query in packet.get("queries", ()):
        if query.get("region") != "public_meld":
            raise ValueError("SIFT experiment accepts public_meld queries only")
        path = (root / query["image_path"]).resolve()
        if root not in path.parents:
            raise ValueError("query image escapes repository root")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != query["image_sha256"]:
            raise ValueError("query image SHA mismatch")
        with Image.open(path) as original:
            image = original.convert("RGB")

        ranked = rank_public_meld_sift(
            bank,
            image,
            source_session=packet["source_session"],
            source_sha256=packet["source_sha256"],
            minimum_other_match_groups=minimum_other_match_groups,
        )
        expected = query["expected_tile"]
        rows.append(
            {
                "query_id": query["query_id"],
                "expected_tile": expected,
                **ranked,
                "top1_correct": ranked["top1_tile"] == expected,
            }
        )

    return {
        "schema_version": "public_meld_sift_query_eval_v0_1",
        "query_count": len(rows),
        "top1_correct_count": sum(bool(row["top1_correct"]) for row in rows),
        "queries": rows,
        "development_only": True,
        "query_only": True,
        "training_template_eligible": False,
        "changes_runtime_behavior": False,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--queries", default=(
        "references/vision/2026-09-30/"
        "first_hand_public_query_features_v0_1.json"
    ))
    parser.add_argument("--minimum-other-match-groups", type=int, default=2)
    args = parser.parse_args()
    report = evaluate_public_meld_sift_queries(
        args.repository_root,
        args.queries,
        minimum_other_match_groups=args.minimum_other_match_groups,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
