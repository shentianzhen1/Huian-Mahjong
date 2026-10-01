"""Validate human-reviewed exact-SHA match bindings before lineage import.

A local SHA hit is not enough to establish original-match lineage. This module
accepts only explicit review records whose SHA is still in the frozen recovery
queue and whose evidence path is a repository-relative existing text record.
It returns validated candidates; it never edits the lineage registry.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Iterable

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def validate_reviewed_bindings(
    records: Iterable[dict[str, Any]],
    *,
    unresolved_shas: set[str],
    repository_root: str | Path,
) -> tuple[list[dict[str, str]], list[str]]:
    root = Path(repository_root).resolve()
    accepted: list[dict[str, str]] = []
    issues: list[str] = []
    seen: dict[str, str] = {}

    for index, row in enumerate(records):
        if not isinstance(row, dict):
            issues.append(f"record_{index}:not_object")
            continue
        if set(row) != {
            "source_sha256",
            "match_group",
            "evidence_path",
            "reviewed",
        }:
            issues.append(f"record_{index}:invalid_fields")
            continue
        sha = row["source_sha256"]
        group = row["match_group"]
        evidence = row["evidence_path"]
        reviewed = row["reviewed"]
        if not isinstance(sha, str) or not _SHA256.fullmatch(sha):
            issues.append(f"record_{index}:invalid_sha")
            continue
        if sha not in unresolved_shas:
            issues.append(f"{sha}:not_in_unresolved_queue")
            continue
        if reviewed is not True:
            issues.append(f"{sha}:not_human_reviewed")
            continue
        if not isinstance(group, str) or not group.strip():
            issues.append(f"{sha}:missing_match_group")
            continue
        if not isinstance(evidence, str) or not evidence.strip():
            issues.append(f"{sha}:missing_evidence_path")
            continue
        relative = Path(evidence)
        if relative.is_absolute():
            issues.append(f"{sha}:absolute_evidence_path_forbidden")
            continue
        resolved = (root / relative).resolve()
        if root != resolved and root not in resolved.parents:
            issues.append(f"{sha}:evidence_path_escape")
            continue
        if not resolved.is_file():
            issues.append(f"{sha}:evidence_path_missing")
            continue
        if resolved.suffix.lower() not in {".json", ".jsonl", ".md", ".txt"}:
            issues.append(f"{sha}:evidence_must_be_reviewable_text")
            continue
        old = seen.get(sha)
        if old is not None and old != group:
            issues.append(f"{sha}:conflicting_match_group")
            continue
        seen[sha] = group
        accepted.append(
            {
                "source_sha256": sha,
                "match_group": group.strip(),
                "evidence_path": evidence,
            }
        )

    if issues:
        return [], issues
    return accepted, []


def load_unresolved_shas(queue_path: str | Path) -> set[str]:
    payload = json.loads(Path(queue_path).read_text(encoding="utf-8"))
    if payload.get("match_group_inference_allowed") is not False:
        raise ValueError("queue must explicitly forbid match-group inference")
    return {
        item["source_sha256"]
        for item in payload.get("items", [])
        if item.get("status") == "UNKNOWN_ORIGINAL_MATCH"
    }
