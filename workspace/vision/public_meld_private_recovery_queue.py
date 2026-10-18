"""Validate the private public-meld recovery queue without private pixels.

The queue records *where* already user-confirmed private crops can be restored.
It never upgrades labels by itself. Source bytes must be re-hashed and the
derived frame/crop lineage re-verified before recovered pixels may enter the
development template bank.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re


SCHEMA_VERSION = "public_meld_private_recovery_queue_v0_1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TILE = re.compile(r"^[MPS][1-9]$|^[ESWNCFP]$")


@dataclass(frozen=True)
class RecoveryItem:
    recovery_id: str
    hand_number: int
    source_file_evidence_name: str
    drive_visible_name: str
    source_sha256_from_repository_evidence: str
    timestamp_seconds: float
    expected_tiles: tuple[str, ...]
    human_label_status: str
    requires_source_sha_recheck: bool
    requires_frame_lineage_verification: bool
    template_eligible_after_pixel_and_lineage_review: bool
    holdout_eligible: bool


@dataclass(frozen=True)
class RecoveryQueue:
    match_group: str
    items: tuple[RecoveryItem, ...]
    development_only: bool
    raw_media_private: bool
    same_match_chunks_are_not_independent: bool


def load_private_recovery_queue(path: str | Path) -> RecoveryQueue:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported recovery queue schema")
    if payload.get("development_only") is not True:
        raise ValueError("recovery queue must remain development-only")
    if payload.get("raw_media_private") is not True:
        raise ValueError("raw media privacy contract changed")
    if payload.get("same_match_chunks_are_not_independent") is not True:
        raise ValueError("same-match independence contract changed")
    match_group = payload.get("match_group")
    if not isinstance(match_group, str) or not match_group:
        raise ValueError("match_group is required")

    rows = payload.get("items")
    if not isinstance(rows, list) or not rows:
        raise ValueError("recovery queue requires items")

    items = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("recovery item must be an object")
        recovery_id = row.get("recovery_id")
        if not isinstance(recovery_id, str) or not recovery_id or recovery_id in seen:
            raise ValueError("recovery_id must be unique and nonempty")
        seen.add(recovery_id)

        hand_number = row.get("hand_number")
        if isinstance(hand_number, bool) or not isinstance(hand_number, int) or not 1 <= hand_number <= 8:
            raise ValueError("hand_number must be 1..8")
        timestamp = row.get("timestamp_seconds")
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or timestamp < 0:
            raise ValueError("timestamp_seconds must be nonnegative numeric")
        digest = row.get("source_sha256_from_repository_evidence")
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise ValueError("repository source SHA256 is invalid")
        expected = row.get("expected_tiles")
        if (
            not isinstance(expected, list)
            or len(expected) != 3
            or any(not isinstance(tile, str) or not _TILE.fullmatch(tile) for tile in expected)
        ):
            raise ValueError("expected_tiles must be three Mahjong tile IDs")
        if row.get("requires_source_sha_recheck") is not True:
            raise ValueError("source SHA must be rechecked before recovery")
        if row.get("requires_frame_lineage_verification") is not True:
            raise ValueError("frame lineage must be verified before recovery")
        if row.get("template_eligible_after_pixel_and_lineage_review") is not True:
            raise ValueError("template eligibility must remain conditional")
        if row.get("holdout_eligible") is not False:
            raise ValueError("reviewed recovery material cannot be holdout evidence")

        items.append(
            RecoveryItem(
                recovery_id=recovery_id,
                hand_number=hand_number,
                source_file_evidence_name=str(row.get("source_file_evidence_name", "")),
                drive_visible_name=str(row.get("drive_visible_name", "")),
                source_sha256_from_repository_evidence=digest,
                timestamp_seconds=float(timestamp),
                expected_tiles=tuple(expected),
                human_label_status=str(row.get("human_label_status", "")),
                requires_source_sha_recheck=True,
                requires_frame_lineage_verification=True,
                template_eligible_after_pixel_and_lineage_review=True,
                holdout_eligible=False,
            )
        )

    runtime = payload.get("runtime_policy")
    if not isinstance(runtime, dict):
        raise ValueError("runtime_policy is required")
    for key in ("changes_runtime_behavior", "formal_promotion_evidence", "safe_for_hint", "safe_for_executor"):
        if runtime.get(key) is not False:
            raise ValueError(f"{key} must remain false")

    return RecoveryQueue(
        match_group=match_group,
        items=tuple(items),
        development_only=True,
        raw_media_private=True,
        same_match_chunks_are_not_independent=True,
    )


def qualify_recovered_item(
    item: RecoveryItem,
    *,
    actual_source_sha256: str,
    pixel_crop_matches_review_packet: bool,
    frame_lineage_verified: bool,
) -> bool:
    """Return template eligibility; fail closed on any provenance mismatch."""
    if not isinstance(actual_source_sha256, str) or not _SHA256.fullmatch(actual_source_sha256):
        raise ValueError("actual_source_sha256 must be lowercase SHA256")
    if actual_source_sha256 != item.source_sha256_from_repository_evidence:
        return False
    if pixel_crop_matches_review_packet is not True:
        return False
    if frame_lineage_verified is not True:
        return False
    return True
