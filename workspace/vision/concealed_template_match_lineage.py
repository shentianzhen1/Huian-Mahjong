"""Fail-closed original-match lineage for concealed template sources.

Runtime Vision source_session values are storage/session identifiers. They are
not evidence that two templates came from different original matches. This
module only trusts an exact source SHA256 that has an explicit reviewed
match-group mapping.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Iterable

_SCHEMA = "concealed_template_match_lineage_development_v0_1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MATCH_GROUP_ALIASES = {
    "reviewed_match_2026_09_26_first_hand": "reviewed_match_2026_09_26_eight_hand",
    "reviewed_match_2026_09_26_hands_2_to_4": "reviewed_match_2026_09_26_eight_hand",
}


@dataclass(frozen=True)
class ConcealedTemplateSource:
    source_sha256: str
    match_group: str
    evidence_path: str


def canonicalize_match_group(match_group: str) -> str:
    """Collapse reviewed aliases that are known to belong to one original match."""
    if not isinstance(match_group, str) or not match_group.strip():
        raise ValueError("match_group is required")
    group = match_group.strip()
    seen: set[str] = set()
    while group in _MATCH_GROUP_ALIASES:
        if group in seen:
            raise ValueError("cyclic concealed-template match-group alias")
        seen.add(group)
        group = _MATCH_GROUP_ALIASES[group]
    return group


def load_concealed_template_lineage(
    path: str | Path,
) -> dict[str, ConcealedTemplateSource]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != _SCHEMA
        or payload.get("development_only") is not True
        or payload.get("excluded_from_formal_promotion") is not True
        or not isinstance(payload.get("sources"), list)
    ):
        raise ValueError("expected concealed-template development lineage registry")

    result: dict[str, ConcealedTemplateSource] = {}
    for entry in payload["sources"]:
        if (
            not isinstance(entry, dict)
            or set(entry) != {"source_sha256", "match_group", "evidence_path"}
        ):
            raise ValueError("concealed-template lineage entry fields do not match schema")
        sha = entry["source_sha256"]
        group = entry["match_group"]
        evidence = entry["evidence_path"]
        if (
            not isinstance(sha, str)
            or not _SHA256.fullmatch(sha)
            or not isinstance(group, str)
            or not group.strip()
            or not isinstance(evidence, str)
            or not evidence.strip()
            or Path(evidence).is_absolute()
        ):
            raise ValueError("invalid concealed-template lineage entry")
        canonical_group = canonicalize_match_group(group)
        old = result.get(sha)
        if old is not None and old.match_group != canonical_group:
            raise ValueError("same source SHA assigned to conflicting match groups")
        result[sha] = ConcealedTemplateSource(sha, canonical_group, evidence)

    if not result:
        raise ValueError("concealed-template lineage registry is empty")
    return result


def qualify_concealed_template_labels(
    labels: Iterable[dict[str, Any]],
    lineage_by_sha: dict[str, ConcealedTemplateSource],
    *,
    query_match_group: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Keep only labels with exact-SHA original-match lineage.

    source_session is deliberately not used as an independence signal. A label
    whose source SHA is absent from the reviewed lineage registry is excluded,
    even if its session name looks unique. Reviewed aliases of one original
    match are collapsed before same-match exclusion.
    """
    if not isinstance(query_match_group, str) or not query_match_group.strip():
        raise ValueError("query_match_group is required")
    canonical_query_group = canonicalize_match_group(query_match_group)

    accepted: list[dict[str, Any]] = []
    missing_lineage = 0
    same_match = 0
    malformed_sha = 0
    represented_groups: set[str] = set()

    for row in labels:
        sha = row.get("sha256")
        if not isinstance(sha, str) or not _SHA256.fullmatch(sha):
            malformed_sha += 1
            continue
        source = lineage_by_sha.get(sha)
        if source is None:
            missing_lineage += 1
            continue
        source_group = canonicalize_match_group(source.match_group)
        if source_group == canonical_query_group:
            same_match += 1
            continue
        copied = dict(row)
        copied["_original_match_group"] = source_group
        accepted.append(copied)
        represented_groups.add(source_group)

    return accepted, {
        "input_label_count": (
            len(labels) if isinstance(labels, (list, tuple)) else None
        ),
        "lineage_qualified_label_count": len(accepted),
        "excluded_missing_original_match_lineage_count": missing_lineage,
        "excluded_same_original_match_count": same_match,
        "excluded_malformed_source_sha_count": malformed_sha,
        "qualified_original_match_group_count": len(represented_groups),
        "lineage_key": "exact_source_sha256",
        "source_session_used_as_independence_signal": False,
        "development_only": True,
        "formal_promotion_evidence": False,
    }


def verify_lineage_evidence_paths(
    registry: dict[str, ConcealedTemplateSource],
    repository_root: str | Path,
) -> list[str]:
    root = Path(repository_root).resolve()
    issues: list[str] = []
    for source in registry.values():
        path = (root / source.evidence_path).resolve()
        if root != path and root not in path.parents:
            issues.append(f"path_escape:{source.source_sha256}")
        elif not path.is_file():
            issues.append(f"missing_evidence:{source.source_sha256}")
    return issues
