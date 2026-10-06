"""Validate raw-source checks for private public-meld recovery items.

A source check only answers whether the currently accessible raw file is exactly
the source bytes recorded by repository evidence. It does not verify frame
lineage, crop pixels, tile identity, or template eligibility.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re


SCHEMA_VERSION = "public_meld_private_recovery_source_check_v0_1"
SOURCE_SHA_VERIFIED = "SOURCE_SHA_VERIFIED"
BLOCKED_SOURCE_SHA_MISMATCH = "BLOCKED_SOURCE_SHA_MISMATCH"
_ALLOWED = {SOURCE_SHA_VERIFIED, BLOCKED_SOURCE_SHA_MISMATCH}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class RecoverySourceCheck:
    recovery_id: str
    drive_visible_name: str
    observed_size_bytes: int
    expected_source_sha256: str
    observed_source_sha256: str
    status: str


def load_recovery_source_checks(
    path: str | Path,
) -> dict[str, RecoverySourceCheck]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported recovery source-check schema")
    if payload.get("method") != "connected_drive_raw_bytes_sha256":
        raise ValueError("source-check method changed")

    rows = payload.get("items")
    if not isinstance(rows, list) or not rows:
        raise ValueError("source-check manifest requires items")

    result: dict[str, RecoverySourceCheck] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("source-check item must be an object")
        recovery_id = row.get("recovery_id")
        if not isinstance(recovery_id, str) or not recovery_id:
            raise ValueError("source-check recovery_id is required")
        if recovery_id in result:
            raise ValueError("duplicate source-check recovery_id")
        size = row.get("observed_size_bytes")
        if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
            raise ValueError("observed_size_bytes must be positive integer")
        expected = row.get("expected_source_sha256")
        observed = row.get("observed_source_sha256")
        if (
            not isinstance(expected, str)
            or not _SHA256.fullmatch(expected)
            or not isinstance(observed, str)
            or not _SHA256.fullmatch(observed)
        ):
            raise ValueError("source-check hashes must be lowercase SHA256")
        status = row.get("status")
        if status not in _ALLOWED:
            raise ValueError("unsupported source-check status")
        if status == SOURCE_SHA_VERIFIED and expected != observed:
            raise ValueError("verified source check has mismatched SHA")
        if status == BLOCKED_SOURCE_SHA_MISMATCH and expected == observed:
            raise ValueError("blocked source mismatch has equal SHA")
        result[recovery_id] = RecoverySourceCheck(
            recovery_id=recovery_id,
            drive_visible_name=str(row.get("drive_visible_name", "")),
            observed_size_bytes=size,
            expected_source_sha256=expected,
            observed_source_sha256=observed,
            status=status,
        )

    runtime = payload.get("runtime_policy")
    if not isinstance(runtime, dict):
        raise ValueError("runtime_policy is required")
    for key in (
        "changes_runtime_behavior",
        "formal_promotion_evidence",
        "safe_for_hint",
        "safe_for_executor",
    ):
        if runtime.get(key) is not False:
            raise ValueError(f"{key} must remain false")
    return result
