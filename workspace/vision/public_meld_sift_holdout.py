"""Blind holdout evaluator for the frozen public-meld SIFT candidate.

This evaluator exists only for a genuinely new independent original match that
was not used while selecting the SIFT candidate. It does not tune parameters,
add holdout pixels to the template bank, define a production confidence
threshold, or change Runtime/Hint/Executor behavior.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from workspace.vision.public_identity_labels import (
    approved_labels,
    load_public_identity_manifest,
)
from workspace.vision.public_identity_shadow_v0_2 import (
    load_development_sources,
)
from workspace.vision.public_meld_identity_sift import (
    PublicMeldSiftBank,
    build_public_meld_sift_bank,
    rank_public_meld_sift,
)
from workspace.vision.public_meld_private_sift_loader import (
    augment_public_meld_sift_bank_from_private_zip,
)
from workspace.vision.public_meld_sift_candidate import (
    assert_future_sift_holdout_eligible,
    load_public_meld_sift_candidate,
)


QUERY_SCHEMA = "public_identity_query_images_v0_1"


def _load_sift_holdout_packet(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != QUERY_SCHEMA:
        raise ValueError("unsupported public meld SIFT holdout packet")
    if payload.get("development_only") is not True:
        raise ValueError("SIFT holdout packet must remain development_only")
    if payload.get("query_only") is not True:
        raise ValueError("SIFT holdout packet must be query_only")
    if payload.get("excluded_from_formal_promotion") is not True:
        raise ValueError("SIFT holdout packet must stay excluded from formal promotion")
    if payload.get("training_template_eligible") is not False:
        raise ValueError("SIFT holdout query pixels must not be template eligible")

    for key in ("source_session", "source_sha256", "match_group"):
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise ValueError(f"SIFT holdout packet requires {key}")

    queries = payload.get("queries")
    if not isinstance(queries, list) or not queries:
        raise ValueError("SIFT holdout packet requires queries")
    query_ids: set[str] = set()
    for row in queries:
        if not isinstance(row, dict):
            raise ValueError("SIFT holdout query row must be an object")
        if row.get("region") != "public_meld":
            raise ValueError("SIFT holdout accepts public_meld queries only")
        for key in ("query_id", "expected_tile", "image_path", "image_sha256"):
            if not isinstance(row.get(key), str) or not row[key]:
                raise ValueError(f"SIFT holdout query requires {key}")
        if row["query_id"] in query_ids:
            raise ValueError("duplicate SIFT holdout query_id")
        query_ids.add(row["query_id"])

    return payload


def _assert_no_template_leakage(
    packet: dict[str, Any],
    *,
    manifest: Any,
) -> None:
    """Reject a holdout if any query source/pixel is already a public template."""
    template_paths = {
        label.image_path
        for label in approved_labels(manifest)
        if label.region == "public_meld"
    }
    template_image_hashes = {
        label.image_sha256
        for label in approved_labels(manifest)
        if label.region == "public_meld"
    }
    template_source_sessions = {
        label.source_session
        for label in approved_labels(manifest)
        if label.region == "public_meld"
    }
    template_source_hashes = {
        label.source_sha256
        for label in approved_labels(manifest)
        if label.region == "public_meld"
    }

    if packet["source_session"] in template_source_sessions:
        raise ValueError("SIFT holdout source session already supplies templates")
    if packet["source_sha256"] in template_source_hashes:
        raise ValueError("SIFT holdout source video already supplies templates")

    for query in packet["queries"]:
        if query["image_path"] in template_paths:
            raise ValueError("SIFT holdout query path is already a template")
        if query["image_sha256"] in template_image_hashes:
            raise ValueError("SIFT holdout query pixels are already a template")


def _assert_no_augmented_bank_source_leakage(
    packet: dict[str, Any],
    *,
    bank: PublicMeldSiftBank,
) -> None:
    """Include local private templates in source/match leakage checks."""
    template_source_hashes = {
        template.source_sha256 for template in bank.templates
    }
    template_match_groups = {
        template.match_group for template in bank.templates
    }
    if packet["source_sha256"] in template_source_hashes:
        raise ValueError(
            "SIFT holdout source video already supplies public/private templates"
        )
    if packet["match_group"] in template_match_groups:
        raise ValueError(
            "SIFT holdout match group already supplies public/private templates"
        )


def evaluate_frozen_public_meld_sift_holdout(
    repository_root: str | Path,
    query_packet_path: str | Path,
    *,
    candidate_path: str | Path = (
        "references/vision/2026-10-01/"
        "public_meld_sift_candidate_v0_1.json"
    ),
    identity_manifest_path: str | Path = (
        "references/vision/2026-09-22/public_identity_labels_v0_1.json"
    ),
    registry_path: str | Path = (
        "references/vision/2026-09-24/"
        "public_identity_source_groups.development.json"
    ),
    private_template_zip_path: str | Path | None = None,
    private_recovery_result_path: str | Path = (
        "references/vision/2026-10-01/"
        "public_meld_private_recovery_result_v0_1.json"
    ),
) -> dict[str, Any]:
    """Score a frozen SIFT candidate on a genuinely new query-only match."""
    root = Path(repository_root).resolve()
    packet = _load_sift_holdout_packet(root / query_packet_path)
    candidate = load_public_meld_sift_candidate(root / candidate_path)
    manifest = load_public_identity_manifest(root / identity_manifest_path)
    sources = load_development_sources(root / registry_path)

    source = sources.get(packet["source_session"])
    if source is None:
        raise ValueError("SIFT holdout source session is not in locked registry")
    if source.source_sha256 != packet["source_sha256"]:
        raise ValueError("SIFT holdout source SHA conflicts with locked registry")
    if source.match_group != packet["match_group"]:
        raise ValueError("SIFT holdout match group conflicts with locked registry")

    assert_future_sift_holdout_eligible(
        candidate,
        holdout_match_group=source.match_group,
        candidate_changed_after_freeze=False,
        query_pixels_used_as_templates=False,
    )
    _assert_no_template_leakage(packet, manifest=manifest)

    bank = build_public_meld_sift_bank(
        manifest,
        root,
        root / registry_path,
    )
    private_load_report = None
    if private_template_zip_path is not None:
        bank, private_load_report = augment_public_meld_sift_bank_from_private_zip(
            bank,
            private_zip_path=private_template_zip_path,
            recovery_result_path=root / private_recovery_result_path,
            repository_root=root,
        )
    _assert_no_augmented_bank_source_leakage(packet, bank=bank)

    from PIL import Image

    rows: list[dict[str, Any]] = []
    for query in packet["queries"]:
        image_path = (root / query["image_path"]).resolve()
        if root not in image_path.parents:
            raise ValueError("SIFT holdout image escapes repository root")
        if not image_path.is_file():
            raise ValueError(f"missing SIFT holdout image: {query['query_id']}")
        digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
        if digest != query["image_sha256"]:
            raise ValueError(f"SIFT holdout image SHA mismatch: {query['query_id']}")

        with Image.open(image_path) as original:
            image = original.convert("RGB")

        ranking = rank_public_meld_sift(
            bank,
            image,
            source_session=packet["source_session"],
            source_sha256=packet["source_sha256"],
            minimum_other_match_groups=candidate.minimum_other_match_groups,
        )
        expected = query["expected_tile"]
        rows.append({
            "query_id": query["query_id"],
            "expected_tile": expected,
            **ranking,
            "top1_correct": ranking["top1_tile"] == expected,
        })

    top1_correct = sum(bool(row["top1_correct"]) for row in rows)
    return {
        "schema_version": "public_meld_sift_holdout_eval_v0_2",
        "candidate_id": candidate.candidate_id,
        "candidate_frozen_on": candidate.frozen_on,
        "candidate_changed_after_freeze": False,
        "holdout_match_group": packet["match_group"],
        "holdout_source_session": packet["source_session"],
        "query_count": len(rows),
        "top1_correct_count": top1_correct,
        "top1_accuracy": (
            round(top1_correct / len(rows), 6) if rows else None
        ),
        "queries": rows,
        "private_template_load": private_load_report,
        "holdout_eligible_under_frozen_candidate_contract": True,
        "development_only": True,
        "source_disjoint_holdout": True,
        "query_pixels_template_eligible": False,
        "changes_runtime_behavior": False,
        "runtime_promotion_decision": "NOT_DECIDED",
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--queries", required=True)
    parser.add_argument("--candidate", default=(
        "references/vision/2026-10-01/"
        "public_meld_sift_candidate_v0_1.json"
    ))
    parser.add_argument("--manifest", default=(
        "references/vision/2026-09-22/public_identity_labels_v0_1.json"
    ))
    parser.add_argument("--registry", default=(
        "references/vision/2026-09-24/"
        "public_identity_source_groups.development.json"
    ))
    parser.add_argument(
        "--private-template-zip",
        help="local private reviewed template ZIP; must remain outside repository",
    )
    parser.add_argument(
        "--private-recovery-result",
        default=(
            "references/vision/2026-10-01/"
            "public_meld_private_recovery_result_v0_1.json"
        ),
    )
    args = parser.parse_args()

    report = evaluate_frozen_public_meld_sift_holdout(
        args.repository_root,
        args.queries,
        candidate_path=args.candidate,
        identity_manifest_path=args.manifest,
        registry_path=args.registry,
        private_template_zip_path=args.private_template_zip,
        private_recovery_result_path=args.private_recovery_result,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
