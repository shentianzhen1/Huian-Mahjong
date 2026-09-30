"""Issue #69: bridge normalized public meld faces into the strict identity gate.

This module does not introduce a new classifier. It reuses the existing
source-disjoint development public-identity gate on the normalized face crops
produced by public_meld_face_segmentation.

A three-face meld is runtime-trusted only when every face independently emits a
read_only_runtime_candidate under the existing thresholds. Action semantics
remain UNKNOWN and Executor is always forbidden.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from workspace.vision.public_identity_shadow_v0_2 import (
    ShadowBank,
    propose_shadow_identity,
)
from workspace.vision.public_meld_face_segmentation import (
    PreparedPublicMeldFaces,
    prepare_public_meld_faces,
)
from workspace.vision.public_tile_detector import PublicGeometryCandidate


@dataclass(frozen=True)
class PublicMeldIdentityBridgeResult:
    prepared: PreparedPublicMeldFaces
    face_results: tuple[dict[str, Any], ...]
    tile_ids: tuple[str | None, ...]
    trusted_for_read_only_runtime: bool
    issues: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "public_meld_identity_bridge_v0_1",
            "geometry": self.prepared.geometry.to_dict(),
            "face_results": [dict(result) for result in self.face_results],
            "tile_ids": [
                tile_id if tile_id is not None else "UNKNOWN"
                for tile_id in self.tile_ids
            ],
            "trusted_for_read_only_runtime": self.trusted_for_read_only_runtime,
            "action_kind": "UNKNOWN",
            "formal_promotion_evidence": False,
            "safe_for_executor": False,
            "issues": list(self.issues),
        }


def classify_public_meld_group(
    image: Any,
    group: PublicGeometryCandidate,
    *,
    bank: ShadowBank,
    source_session: str,
    source_sha256: str,
    minimum_score: float = 0.93,
    minimum_margin: float = 0.075,
) -> PublicMeldIdentityBridgeResult:
    """Normalize/split one meld group, then run the existing public identity gate.

    STACKED/UNKNOWN geometry is not forced through a three-face classifier.
    For FLAT rows, all three faces are evaluated independently in the
    public_meld region. A partially accepted row remains untrusted as a whole;
    accepted individual candidates are retained only as diagnostics.
    """
    prepared = prepare_public_meld_faces(image, group)
    if len(prepared.face_images) != 3:
        reason = (
            "stacked_meld_identity_split_not_implemented"
            if prepared.geometry.stack_state == "STACKED"
            else "meld_geometry_not_classifier_ready"
        )
        return PublicMeldIdentityBridgeResult(
            prepared=prepared,
            face_results=(),
            tile_ids=(),
            trusted_for_read_only_runtime=False,
            issues=(reason,),
        )

    face_results: list[dict[str, Any]] = []
    tile_ids: list[str | None] = []
    for face in prepared.face_images:
        result = propose_shadow_identity(
            bank,
            face,
            region="public_meld",
            source_session=source_session,
            source_sha256=source_sha256,
            minimum_score=minimum_score,
            minimum_margin=minimum_margin,
        )
        face_results.append(result)
        candidate = result.get("read_only_runtime_candidate")
        trusted = bool(
            isinstance(candidate, str)
            and candidate
            and result.get("safe_for_runtime") is True
            and result.get("safe_for_executor") is False
            and result.get("formal_promotion_evidence") is False
            and result.get("winner_independent_match_groups", 0) >= 2
            and result.get("eligible_class_count", 0) >= 2
        )
        tile_ids.append(candidate if trusted else None)

    all_trusted = len(tile_ids) == 3 and all(tile_id is not None for tile_id in tile_ids)
    issues: list[str] = []
    if not all_trusted:
        issues.append("one_or_more_meld_faces_untrusted")

    return PublicMeldIdentityBridgeResult(
        prepared=prepared,
        face_results=tuple(face_results),
        tile_ids=tuple(tile_ids),
        trusted_for_read_only_runtime=all_trusted,
        issues=tuple(issues),
    )
