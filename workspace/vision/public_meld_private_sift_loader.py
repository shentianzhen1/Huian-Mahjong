"""Local-only loader for recovered private public-meld SIFT templates.

Private PNGs remain outside the public repository. The loader accepts only a
ZIP whose reviewed-label manifest hash is pinned by repository recovery
metadata, then verifies source/frame/tile/crop hashes before extracting SIFT
descriptors.

This augments development-only SIFT banks. It does not alter Runtime, Hint,
Executor, promotion evidence, or holdout eligibility.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import ZipFile

from workspace.vision.public_identity_shadow_v0_2 import SourceGroup
from workspace.vision.public_meld_identity_sift import (
    PublicMeldSiftBank,
    PublicMeldSiftTemplate,
    _sift_descriptors,
)
from workspace.vision.public_meld_private_recovery_result import (
    RecoveredPrivateTemplate,
    load_private_recovery_results,
)


_PRIVATE_SCHEMA = "private_existing_user_confirmed_public_faces_v0_1"
_PRIVATE_VERIFICATION = (
    "nine_original_videos_rehashed_and_all_36_png_exact_pixel_matched"
)


def _safe_private_crop_path(crop_file: str) -> str:
    path = PurePosixPath(crop_file)
    if (
        not crop_file
        or path.is_absolute()
        or ".." in path.parts
        or len(path.parts) != 1
        or path.name != crop_file
    ):
        raise ValueError("private crop_file must be a simple filename")
    return "approved_faces/" + crop_file


def _validate_private_manifest(payload: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(payload, dict) or payload.get("schema_version") != _PRIVATE_SCHEMA:
        raise ValueError("unsupported private approved-label schema")
    expected = {
        "image_source_verification": _PRIVATE_VERIFICATION,
        "development_only": True,
        "previously_inspected": True,
        "independent_blind_review": False,
        "source_disjoint_holdout": False,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_executor": False,
    }
    for field, value in expected.items():
        if payload.get(field) != value:
            raise ValueError(f"private approved-label contract changed: {field}")
    groups = payload.get("groups")
    if not isinstance(groups, list) or not groups:
        raise ValueError("private approved-label manifest requires groups")
    return tuple(groups)


def _matching_private_group(
    groups: tuple[dict[str, Any], ...],
    recovered: RecoveredPrivateTemplate,
) -> dict[str, Any]:
    matches = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        if group.get("video_sha256") != recovered.source_sha256:
            continue
        if group.get("frame_index") != recovered.frame_index:
            continue
        timestamp = group.get("timestamp_seconds")
        if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool):
            continue
        if abs(float(timestamp) - recovered.timestamp_seconds) > 1e-6:
            continue
        faces = group.get("faces")
        if not isinstance(faces, list) or len(faces) != len(recovered.tile_ids):
            continue
        tile_ids = tuple(face.get("approved_tile_id") for face in faces)
        crop_hashes = tuple(face.get("crop_sha256") for face in faces)
        if tile_ids != recovered.tile_ids or crop_hashes != recovered.crop_sha256:
            continue
        matches.append(group)
    if len(matches) != 1:
        raise ValueError("recovered private group not found uniquely in pinned manifest")
    return matches[0]


def augment_public_meld_sift_bank_from_private_zip(
    bank: PublicMeldSiftBank,
    *,
    private_zip_path: str | Path,
    recovery_result_path: str | Path,
    repository_root: str | Path,
) -> tuple[PublicMeldSiftBank, dict[str, Any]]:
    """Add fully recovered private development templates to a SIFT bank."""
    from PIL import Image

    root = Path(repository_root).resolve()
    zip_path = Path(private_zip_path).resolve()
    if zip_path == root or root in zip_path.parents:
        raise ValueError("private template ZIP must remain outside repository")
    if not zip_path.is_file():
        raise ValueError("private template ZIP is missing")

    recovered_results = [
        item
        for item in load_private_recovery_results(recovery_result_path).values()
        if isinstance(item, RecoveredPrivateTemplate)
    ]
    if not recovered_results:
        return bank, {
            "schema_version": "public_meld_private_sift_load_v0_1",
            "private_template_count": 0,
            "recovery_ids": [],
            "tile_ids": [],
            "changes_runtime_behavior": False,
            "formal_promotion_evidence": False,
            "safe_for_runtime": False,
            "safe_for_hint": False,
            "safe_for_executor": False,
        }

    expected_manifest_hashes = {
        item.private_label_manifest_sha256 for item in recovered_results
    }
    expected_manifest_names = {
        item.private_label_manifest_name for item in recovered_results
    }
    if len(expected_manifest_hashes) != 1 or len(expected_manifest_names) != 1:
        raise ValueError("recovered private templates disagree on pinned manifest")
    manifest_name = next(iter(expected_manifest_names))
    expected_manifest_hash = next(iter(expected_manifest_hashes))

    sources = dict(bank.sources)
    templates = list(bank.templates)
    loaded_ids: list[str] = []
    loaded_tiles: list[str] = []

    with ZipFile(zip_path, "r") as archive:
        try:
            manifest_bytes = archive.read(manifest_name)
        except KeyError as exc:
            raise ValueError("pinned private label manifest missing from ZIP") from exc
        actual_manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
        if actual_manifest_hash != expected_manifest_hash:
            raise ValueError("private label manifest SHA mismatch")
        try:
            payload = json.loads(manifest_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("private label manifest is invalid JSON") from exc
        groups = _validate_private_manifest(payload)

        for recovered in recovered_results:
            group = _matching_private_group(groups, recovered)
            session = "private_recovered_" + recovered.recovery_id
            if session in sources:
                raise ValueError("private recovery session already loaded")
            sources[session] = SourceGroup(
                session=session,
                source_sha256=recovered.source_sha256,
                match_group=recovered.match_group,
            )

            faces = group["faces"]
            for index, face in enumerate(faces):
                crop_file = face.get("crop_file")
                if not isinstance(crop_file, str):
                    raise ValueError("private recovered face lacks crop_file")
                archive_path = _safe_private_crop_path(crop_file)
                try:
                    raw = archive.read(archive_path)
                except KeyError as exc:
                    raise ValueError("private recovered crop missing from ZIP") from exc
                crop_hash = hashlib.sha256(raw).hexdigest()
                if crop_hash != recovered.crop_sha256[index]:
                    raise ValueError("private recovered crop SHA mismatch")
                with Image.open(io.BytesIO(raw)) as original:
                    image = original.convert("RGB")
                descriptors = _sift_descriptors(image)
                if descriptors is None:
                    raise ValueError("private recovered crop lacks SIFT descriptors")
                templates.append(
                    PublicMeldSiftTemplate(
                        tile_id=recovered.tile_ids[index],
                        source_session=session,
                        source_sha256=recovered.source_sha256,
                        match_group=recovered.match_group,
                        descriptors=descriptors,
                    )
                )
                loaded_tiles.append(recovered.tile_ids[index])
            loaded_ids.append(recovered.recovery_id)

    augmented = PublicMeldSiftBank(
        sources=sources,
        templates=tuple(templates),
    )
    return augmented, {
        "schema_version": "public_meld_private_sift_load_v0_1",
        "private_template_count": len(loaded_tiles),
        "recovery_ids": sorted(loaded_ids),
        "tile_ids": sorted(loaded_tiles),
        "private_pixels_committed_to_repository": False,
        "source_disjoint_holdout": False,
        "changes_runtime_behavior": False,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }
