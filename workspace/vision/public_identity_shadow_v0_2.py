"""Issue #69: separate-region, development-only public identity shadow probe.

Never reuse hand/draw/gold templates or write predictions into RiverSnapshot,
MeldSnapshot, Timeline, Hint or Executor. Previously reviewed images are useful
for testing intake, NOT for reporting live or source-disjoint accuracy.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from workspace.vision.public_identity_labels import (
    PUBLIC_REGIONS, PublicIdentityManifest, approved_labels,
    load_public_identity_manifest, pixel_bbox, verify_repository_files,
)

_SHA = re.compile(r"^[0-9a-f]{64}$")
_SCHEMA = "public_identity_source_groups_development_v0_1"
UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SourceGroup:
    session: str
    source_sha256: str
    match_group: str


@dataclass(frozen=True)
class PublicTemplate:
    region: str
    tile_id: str
    source_session: str
    source_sha256: str
    match_group: str
    feature: Any  # numpy array: keep Vision extras optional in core installs


@dataclass(frozen=True)
class ShadowBank:
    sources: dict[str, SourceGroup]
    templates: tuple[PublicTemplate, ...]


def load_development_sources(path: str | Path) -> dict[str, SourceGroup]:
    """An explicit match group is required: different clips != different matches."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if (not isinstance(payload, dict)
            or payload.get("schema_version") != _SCHEMA
            or payload.get("development_only") is not True
            or payload.get("excluded_from_formal_promotion") is not True
            or not isinstance(payload.get("sources"), list)):
        raise ValueError("expected source-group development registry")
    sources: dict[str, SourceGroup] = {}
    group_by_sha: dict[str, str] = {}
    for entry in payload["sources"]:
        if (not isinstance(entry, dict) or set(entry) != {
                "source_session", "source_sha256", "match_group", "review_exposure"
        } or entry["review_exposure"] != "previously_inspected"):
            raise ValueError("source must be a reviewed development-only recording")
        session, sha, group = (
            entry["source_session"], entry["source_sha256"], entry["match_group"]
        )
        if (not all(isinstance(x, str) and x for x in (session, sha, group))
                or not _SHA.fullmatch(sha)):
            raise ValueError("source requires exact session, SHA256 and match group")
        if session in sources:
            raise ValueError("duplicate source session")
        if sha in group_by_sha and group_by_sha[sha] != group:
            raise ValueError("identical video bytes assigned to different matches")
        sources[session] = SourceGroup(session, sha, group)
        group_by_sha[sha] = group
    if not sources:
        raise ValueError("no development sources")
    return sources


def _feature(image: Any) -> Any | None:
    """Normalize only public-face pixels; constant/blank crops abstain."""
    import numpy as np
    from PIL import Image

    gray = image.convert("L").resize((32, 48), Image.Resampling.BILINEAR)
    values = np.asarray(gray, dtype=np.float32)[2:-2, 2:-2].copy()
    values -= values.mean()
    length = float(np.linalg.norm(values))
    if length < 1e-5:
        return None
    return (values / length).ravel()


def build_shadow_bank(
    manifest: PublicIdentityManifest, repository_root: str | Path,
    registry_path: str | Path,
) -> ShadowBank:
    """Verify committed image SHA before any reviewed face can enter a bank."""
    from PIL import Image

    if not manifest.excluded_from_formal_promotion:
        raise ValueError("shadow bank accepts development-only public labels")
    sources = load_development_sources(registry_path)
    issues = verify_repository_files(manifest, repository_root)
    if issues:
        raise ValueError("source image integrity failed: " + ",".join(issues))
    root = Path(repository_root).resolve()
    templates: list[PublicTemplate] = []
    for label in approved_labels(manifest):
        source = sources.get(label.source_session)
        if source is None or source.source_sha256 != label.source_sha256:
            raise ValueError("public label source-group/SHA mismatch")
        image_path = (root / label.image_path).resolve()
        if root not in image_path.parents:
            raise ValueError("public label path escapes repository root")
        with Image.open(image_path) as original:
            image = original.convert("RGB")
            x, y, width, height = pixel_bbox(label, image.size)
            feature = _feature(image.crop((x, y, x + width, y + height)))
        if feature is None:
            # No empty/constant source crop becomes an identity template.
            continue
        templates.append(PublicTemplate(
            label.region, label.tile_id, label.source_session,
            label.source_sha256, source.match_group, feature,
        ))
    return ShadowBank(sources, tuple(templates))


def propose_shadow_identity(
    bank: ShadowBank, image: Any, *, region: str,
    source_session: str, source_sha256: str,
    minimum_score: float = 0.93, minimum_margin: float = 0.075,
) -> dict[str, Any]:
    """Propose a class only with two *other* match groups per class.

    At least two independently supported competing classes must exist in the
    SAME public region. Output tile_id is always UNKNOWN, including proposals.
    This is a development-only diagnostic and must never feed live actions.
    """
    import numpy as np

    if region not in PUBLIC_REGIONS:
        raise ValueError("public identity region must be explicit")
    source = bank.sources.get(source_session)
    if source is None or source.source_sha256 != source_sha256:
        raise ValueError("query source session/SHA not in locked registry")
    if not 0 < minimum_score <= 1 or not 0 < minimum_margin <= 2:
        raise ValueError("invalid shadow thresholds")
    result: dict[str, Any] = {
        "tile_id": UNKNOWN, "shadow_proposal": None, "region": region,
        "eligible_class_count": 0, "score": None, "margin": None,
        "evidence_grade": UNKNOWN, "safe_for_runtime": False,
        "safe_for_executor": False, "formal_promotion_evidence": False,
        "reason": "insufficient_cross_match_class_support",
    }
    query = _feature(image)
    if query is None:
        result["reason"] = "blank_or_low_texture_public_face"
        return result
    best_by_class_and_group: dict[str, dict[str, float]] = defaultdict(dict)
    for template in bank.templates:
        if (template.region != region
                or template.match_group == source.match_group
                or template.source_sha256 == source_sha256):
            continue
        score = float(np.dot(query, template.feature))
        old = best_by_class_and_group[template.tile_id].get(
            template.match_group, -2.0
        )
        best_by_class_and_group[template.tile_id][template.match_group] = max(
            old, score
        )
    # Second-best *independent match* score, not the score of a near-duplicate
    # screenshot or three faces from the same original video.
    eligible = sorted(
        ((tile, sorted(scores.values(), reverse=True)[1])
         for tile, scores in best_by_class_and_group.items()
         if len(scores) >= 2),
        key=lambda row: (-row[1], row[0]),
    )
    result["eligible_class_count"] = len(eligible)
    if len(eligible) < 2:
        return result
    winner, score = eligible[0]
    margin = score - eligible[1][1]
    result["score"] = round(score, 6)
    result["margin"] = round(margin, 6)
    if score >= minimum_score and margin >= minimum_margin:
        result["shadow_proposal"] = winner
        result["reason"] = "development_shadow_only_not_runtime_identity"
    else:
        result["reason"] = "low_score_or_ambiguous_public_face"
    return result


def evaluate_reviewed_development(
    manifest: PublicIdentityManifest, repository_root: str | Path,
    registry_path: str | Path,
) -> dict[str, Any]:
    """Leave the complete original match group out before scoring each crop."""
    from PIL import Image

    bank = build_shadow_bank(manifest, repository_root, registry_path)
    root = Path(repository_root).resolve()
    by_region = {region: {"reviewed": 0, "proposed": 0, "abstained": 0}
                 for region in sorted(PUBLIC_REGIONS)}
    proposals = 0
    correct = 0
    eligible_queries = 0
    for label in approved_labels(manifest):
        with Image.open(root / label.image_path) as original:
            image = original.convert("RGB")
            x, y, width, height = pixel_bbox(label, image.size)
            crop = image.crop((x, y, x + width, y + height))
        observed = propose_shadow_identity(
            bank, crop, region=label.region,
            source_session=label.source_session,
            source_sha256=label.source_sha256,
        )
        row = by_region[label.region]
        row["reviewed"] += 1
        if observed["eligible_class_count"] >= 2:
            eligible_queries += 1
        if observed["shadow_proposal"] is None:
            row["abstained"] += 1
        else:
            proposals += 1
            row["proposed"] += 1
            correct += observed["shadow_proposal"] == label.tile_id
    return {
        "schema_version": "public_identity_shadow_v0_2",
        "development_only": True, "source_match_groups": len(
            {s.match_group for s in bank.sources.values()}
        ),
        "approved_label_count": len(approved_labels(manifest)),
        "training_templates": len(bank.templates),
        "eligible_queries": eligible_queries,
        "shadow_proposals": proposals,
        "shadow_abstentions": sum(v["abstained"] for v in by_region.values()),
        "shadow_accuracy_on_proposals": (
            round(correct / proposals, 6) if proposals else None
        ),
        "by_region": by_region, "tile_id_policy": UNKNOWN,
        "source_disjoint_holdout": False, "formal_promotion_evidence": False,
        "safe_for_runtime": False, "safe_for_executor": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=(
        "references/vision/2026-09-22/public_identity_labels_v0_1.json"
    ))
    parser.add_argument("--registry", default=(
        "references/vision/2026-09-24/public_identity_source_groups.development.json"
    ))
    parser.add_argument("--repository-root", default=".")
    args = parser.parse_args()
    manifest = load_public_identity_manifest(args.manifest)
    print(json.dumps(evaluate_reviewed_development(
        manifest, args.repository_root, args.registry
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
