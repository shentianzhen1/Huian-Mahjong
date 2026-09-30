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
from typing import Any, Sequence

from workspace.vision.public_identity_shadow_v0_2 import (
    ShadowBank,
    propose_shadow_identity,
)
from workspace.vision.public_meld_face_segmentation import (
    PreparedPublicMeldFaces,
    prepare_public_meld_faces,
)
from workspace.vision.public_tile_detector import PublicGeometryCandidate
from workspace.vision.public_observers import MeldGroup, MeldSnapshot


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

    if not source_session or not source_sha256:
        return PublicMeldIdentityBridgeResult(
            prepared=prepared,
            face_results=(),
            tile_ids=(None, None, None),
            trusted_for_read_only_runtime=False,
            issues=("public_identity_source_scope_missing",),
        )
    source = bank.sources.get(source_session)
    if source is None:
        return PublicMeldIdentityBridgeResult(
            prepared=prepared,
            face_results=(),
            tile_ids=(None, None, None),
            trusted_for_read_only_runtime=False,
            issues=("public_identity_source_not_registered",),
        )
    if source.source_sha256 != source_sha256:
        return PublicMeldIdentityBridgeResult(
            prepared=prepared,
            face_results=(),
            tile_ids=(None, None, None),
            trusted_for_read_only_runtime=False,
            issues=("public_identity_source_sha_conflict",),
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


def meld_snapshot_from_identity_bridges(
    entries: Sequence[
        tuple[PublicGeometryCandidate, PublicMeldIdentityBridgeResult]
    ],
    *,
    actor: str,
    timestamp_seconds: float,
    frame: str | int | None,
    source_session: str,
    stream_epoch: int = 0,
) -> MeldSnapshot:
    """Build one identity-strict meld snapshot for the existing temporal observer.

    Only a frame where EVERY visible meld group has a complete, read-only
    identity is marked trusted. Incomplete/stacked groups are retained as
    UNKNOWN geometry so they cannot disappear silently, but the whole snapshot
    is untrusted and therefore cannot advance MeldSnapshotObserver's
    settle-frame streak.
    """
    groups: list[MeldGroup] = []
    refs: list[str] = []
    if frame is not None:
        refs.append(f"public:{source_session}:frame:{frame}")

    all_complete = bool(entries)
    for group, result in entries:
        if (
            result.trusted_for_read_only_runtime
            and len(result.tile_ids) == 3
            and all(tile is not None for tile in result.tile_ids)
        ):
            tiles = tuple(result.tile_ids)
        elif result.prepared.geometry.stack_state == "STACKED":
            tiles = (None, None, None, None)
            all_complete = False
        else:
            tiles = (None, None, None)
            all_complete = False

        confidence_values = [float(group.confidence)]
        for face_result in result.face_results:
            try:
                score = float(face_result.get("score"))
            except (TypeError, ValueError):
                continue
            confidence_values.append(max(0.0, min(1.0, score)))

        groups.append(
            MeldGroup(
                normalized_bbox=group.normalized_bbox,
                tiles=tiles,
                confidence=min(confidence_values),
                evidence_refs=tuple(refs),
            )
        )

    return MeldSnapshot(
        timestamp_seconds=timestamp_seconds,
        actor=actor,
        groups=tuple(groups),
        frame=frame,
        trusted=all_complete,
        evidence_refs=tuple(refs),
        stream_epoch=stream_epoch,
        source_session=source_session or None,
    )
