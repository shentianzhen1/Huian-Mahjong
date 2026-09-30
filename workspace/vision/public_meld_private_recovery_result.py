"""Validate metadata-only results of private public-meld recovery.

Recovered pixels remain private. This contract records whether a previously
user-reviewed crop was re-verified against the exact original source bytes and
can therefore be used by local development tooling as a private template.

It never makes private pixels public, never creates holdout evidence, and never
changes Runtime/Hint/Executor behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re


SCHEMA_VERSION = "public_meld_private_recovery_result_v0_1"
RECOVERED = "PRIVATE_TEMPLATE_EVIDENCE_RECOVERED"
BLOCKED = "BLOCKED_SOURCE_SHA_MISMATCH"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TILE = re.compile(r"^[MPS][1-9]$|^[ESWNCFP]$")


@dataclass(frozen=True)
class RecoveredPrivateTemplate:
    recovery_id: str
    source_sha256: str
    frame_index: int
    timestamp_seconds: float
    match_group: str
    tile_ids: tuple[str, ...]
    crop_sha256: tuple[str, ...]
    private_template_eligible: bool


@dataclass(frozen=True)
class BlockedPrivateRecovery:
    recovery_id: str
    status: str
    private_template_eligible: bool


def load_private_recovery_results(
    path: str | Path,
) -> dict[str, RecoveredPrivateTemplate | BlockedPrivateRecovery]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported private recovery result schema")

    rows = payload.get("items")
    if not isinstance(rows, list) or not rows:
        raise ValueError("private recovery result requires items")

    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("private recovery result item must be an object")
        recovery_id = row.get("recovery_id")
        if not isinstance(recovery_id, str) or not recovery_id:
            raise ValueError("recovery_id is required")
        if recovery_id in result:
            raise ValueError("duplicate recovery_id")

        status = row.get("status")
        if status == BLOCKED:
            if row.get("private_template_eligible") is not False:
                raise ValueError("blocked recovery cannot be template eligible")
            if row.get("holdout_eligible") is not False:
                raise ValueError("blocked recovery cannot be holdout eligible")
            result[recovery_id] = BlockedPrivateRecovery(
                recovery_id=recovery_id,
                status=status,
                private_template_eligible=False,
            )
            continue

        if status != RECOVERED:
            raise ValueError("unsupported recovery result status")
        source_sha = row.get("source_sha256")
        if not isinstance(source_sha, str) or not _SHA256.fullmatch(source_sha):
            raise ValueError("source_sha256 must be lowercase SHA256")
        frame_index = row.get("frame_index")
        if isinstance(frame_index, bool) or not isinstance(frame_index, int) or frame_index < 0:
            raise ValueError("frame_index must be nonnegative integer")
        timestamp = row.get("timestamp_seconds")
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or timestamp < 0:
            raise ValueError("timestamp_seconds must be nonnegative numeric")
        if row.get("frame_lineage_mode") != "direct_source_frame_no_derivative":
            raise ValueError("recovered private template must use direct source frame lineage")
        if row.get("private_template_eligible") is not True:
            raise ValueError("recovered item must be explicitly template eligible")
        if row.get("public_repo_pixels_committed") is not False:
            raise ValueError("private recovery pixels must not be committed")
        if row.get("holdout_eligible") is not False:
            raise ValueError("recovered development pixels cannot be holdout evidence")
        if row.get("formal_promotion_evidence") is not False:
            raise ValueError("private recovery is not formal promotion evidence")
        if row.get("safe_for_hint") is not False or row.get("safe_for_executor") is not False:
            raise ValueError("private recovery cannot enable Hint/Executor")
        match_group = row.get("match_group")
        if not isinstance(match_group, str) or not match_group:
            raise ValueError("match_group is required")

        faces = row.get("faces")
        if not isinstance(faces, list) or len(faces) != 3:
            raise ValueError("recovered regular meld must have exactly three faces")
        tile_ids = []
        crop_hashes = []
        for face in faces:
            if not isinstance(face, dict):
                raise ValueError("face must be an object")
            tile_id = face.get("tile_id")
            crop_hash = face.get("crop_sha256")
            bbox = face.get("bbox")
            if not isinstance(tile_id, str) or not _TILE.fullmatch(tile_id):
                raise ValueError("invalid tile_id")
            if not isinstance(crop_hash, str) or not _SHA256.fullmatch(crop_hash):
                raise ValueError("invalid crop_sha256")
            if (
                not isinstance(bbox, list)
                or len(bbox) != 4
                or any(isinstance(v, bool) or not isinstance(v, int) for v in bbox)
                or bbox[2] <= 0
                or bbox[3] <= 0
            ):
                raise ValueError("invalid face bbox")
            if face.get("pixel_exact_from_source_frame") is not True:
                raise ValueError("all recovered faces must be pixel-exact")
            tile_ids.append(tile_id)
            crop_hashes.append(crop_hash)

        result[recovery_id] = RecoveredPrivateTemplate(
            recovery_id=recovery_id,
            source_sha256=source_sha,
            frame_index=frame_index,
            timestamp_seconds=float(timestamp),
            match_group=match_group,
            tile_ids=tuple(tile_ids),
            crop_sha256=tuple(crop_hashes),
            private_template_eligible=True,
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
