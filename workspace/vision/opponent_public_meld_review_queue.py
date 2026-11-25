"""Validate the private opponent exposed-meld review queue.

The queue stores only source lineage, human-confirmed expected tile identities,
and candidate time/frame windows. It never stores raw private video pixels and
never promotes an identity prediction into Runtime/Hint/Executor.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SCHEMA = "opponent_public_meld_review_queue_v0_1"


def _is_suited_sequence(tiles: list[str]) -> bool:
    if len(tiles) != 3:
        return False
    suits = {tile[:1] for tile in tiles}
    if len(suits) != 1 or next(iter(suits)) not in {"M", "P", "S"}:
        return False
    try:
        ranks = sorted(int(tile[1:]) for tile in tiles)
    except ValueError:
        return False
    return ranks[1] == ranks[0] + 1 and ranks[2] == ranks[1] + 1


def validate_opponent_public_meld_review_queue(payload: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    if payload.get("schema_version") != _SCHEMA:
        issues.append("schema_version")
    if payload.get("changes_runtime_behavior") is not False:
        issues.append("changes_runtime_behavior")
    if payload.get("formal_promotion_evidence") is not False:
        issues.append("formal_promotion_evidence")
    if payload.get("safe_for_runtime") is not False:
        issues.append("safe_for_runtime")
    if payload.get("safe_for_hint") is not False:
        issues.append("safe_for_hint")
    if payload.get("safe_for_executor") is not False:
        issues.append("safe_for_executor")

    items = payload.get("items")
    if not isinstance(items, list) or not items:
        issues.append("items")
        items = []

    seen: set[str] = set()
    groups: set[str] = set()
    source_verified = 0
    classifier_ready = 0

    for index, row in enumerate(items):
        prefix = f"items[{index}]"
        if not isinstance(row, dict):
            issues.append(prefix)
            continue
        review_id = row.get("review_id")
        if not isinstance(review_id, str) or not review_id:
            issues.append(prefix + ".review_id")
        elif review_id in seen:
            issues.append(prefix + ".duplicate_review_id")
        else:
            seen.add(review_id)

        if row.get("actor") != "opponent":
            issues.append(prefix + ".actor")
        if row.get("event") != "CHI":
            issues.append(prefix + ".event")

        expected = row.get("expected_tiles")
        if not isinstance(expected, list) or not all(
            isinstance(tile, str) for tile in expected
        ) or not _is_suited_sequence(expected):
            issues.append(prefix + ".expected_tiles")

        match_group = row.get("match_group")
        if not isinstance(match_group, str) or not match_group:
            issues.append(prefix + ".match_group")
        else:
            groups.add(match_group)

        sha = row.get("source_sha256")
        if not isinstance(sha, str) or not _SHA256.fullmatch(sha):
            issues.append(prefix + ".source_sha256")

        status = row.get("crop_status")
        if not isinstance(status, str) or not status:
            issues.append(prefix + ".crop_status")
        elif status == "CLASSIFIER_READY":
            classifier_ready += 1

        verification = row.get("source_verification")
        if isinstance(verification, str) and verification.startswith(
            "SHA256_EXACT_VERIFIED"
        ):
            source_verified += 1

    counts = payload.get("current_counts")
    if not isinstance(counts, dict):
        issues.append("current_counts")
        counts = {}
    if counts.get("queued_groups") != len(items):
        issues.append("current_counts.queued_groups")
    if counts.get("independent_original_match_groups") != len(groups):
        issues.append("current_counts.independent_original_match_groups")
    if counts.get("source_verified_groups") != source_verified:
        issues.append("current_counts.source_verified_groups")
    if counts.get("classifier_ready_groups") != classifier_ready:
        issues.append("current_counts.classifier_ready_groups")

    return {
        "schema_version": "opponent_public_meld_review_queue_validation_v0_1",
        "valid": not issues,
        "issues": issues,
        "queued_group_count": len(items),
        "independent_match_group_count": len(groups),
        "source_verified_group_count": source_verified,
        "classifier_ready_group_count": classifier_ready,
        "changes_runtime_behavior": False,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def load_and_validate_opponent_public_meld_review_queue(
    path: str | Path,
) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    result = validate_opponent_public_meld_review_queue(payload)
    if not result["valid"]:
        raise ValueError(
            "invalid opponent public-meld review queue: "
            + ",".join(result["issues"])
        )
    return result
