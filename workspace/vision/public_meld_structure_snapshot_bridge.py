"""Development bridge from public-meld geometry into MeldSnapshot facts.

This layer is geometry-only. It consumes one already-detected public meld
candidate, runs the existing meld normalization, and maps only structural
states into UNKNOWN-identity face counts:

- FLAT -> one 3-face MeldGroup
- STACKED -> one 4-face MeldGroup
- UNKNOWN / unverified source -> untrusted empty snapshot

It never classifies tile identity, CHI/PENG/KONG semantics, Rules, Hint, or
Executor behavior. The output exists only so #69 offline replay can preserve
stable 3 -> 4 public-meld structure changes without inventing an action.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from workspace.vision.public_meld_geometry_normalization import (
    FLAT,
    STACKED,
    UNKNOWN,
    PublicMeldGeometryAnalysis,
    normalize_public_meld_crop,
)
from workspace.vision.public_observers import MeldGroup, MeldSnapshot
from workspace.vision.public_tile_detector import PublicGeometryCandidate


@dataclass(frozen=True)
class PublicMeldStructureSnapshotReview:
    snapshot: MeldSnapshot
    geometry: PublicMeldGeometryAnalysis
    structural_face_count: int | None
    issues: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "schema_version": "public_meld_structure_snapshot_bridge_dev_v0_1",
            "development_only": True,
            "stack_state": self.geometry.stack_state,
            "structural_face_count": self.structural_face_count,
            "snapshot_trusted": self.snapshot.trusted,
            "tile_identity": "UNKNOWN",
            "action_kind": "UNKNOWN",
            "issues": list(self.issues),
            "formal_promotion_evidence": False,
            "safe_for_runtime": False,
            "safe_for_hint": False,
            "safe_for_executor": False,
        }


def _untrusted_snapshot(
    *,
    timestamp_seconds: float,
    actor: str,
    source_session: str,
    stream_epoch: int,
    frame_index: int,
    evidence_refs: Sequence[str],
) -> MeldSnapshot:
    return MeldSnapshot(
        timestamp_seconds=timestamp_seconds,
        actor=actor,
        groups=(),
        frame=frame_index,
        trusted=False,
        evidence_refs=tuple(evidence_refs),
        source_session=source_session,
        stream_epoch=stream_epoch,
    )


def review_public_meld_structure_snapshot(
    image: Any,
    group: PublicGeometryCandidate,
    *,
    timestamp_seconds: float,
    actor: str,
    source_session: str,
    stream_epoch: int,
    frame_index: int,
    source_frame_verified: bool,
    public_meld_region_verified: bool,
    evidence_refs: Sequence[str] = (),
) -> PublicMeldStructureSnapshotReview:
    """Convert one verified public-meld group into an UNKNOWN-friendly snapshot.

    The caller owns source qualification and target-group selection. A positive
    result is structural evidence only; even STACKED never means ADD_KONG by
    itself. Source mismatch or ambiguous geometry fails closed.
    """
    if not isinstance(group, PublicGeometryCandidate):
        raise ValueError("PublicGeometryCandidate required")
    if not isinstance(source_session, str) or not source_session:
        raise ValueError("source_session required")
    if isinstance(stream_epoch, bool) or not isinstance(stream_epoch, int) or stream_epoch < 0:
        raise ValueError("stream_epoch must be a nonnegative integer")
    if isinstance(frame_index, bool) or not isinstance(frame_index, int) or frame_index < 0:
        raise ValueError("frame_index must be a nonnegative integer")
    refs = tuple(str(ref) for ref in evidence_refs if str(ref))

    if (
        source_frame_verified is not True
        or public_meld_region_verified is not True
        or group.geometry_kind not in {"bottom_group", "top_group"}
        or group.frame not in (None, frame_index)
        or group.session not in (None, source_session)
    ):
        geometry = normalize_public_meld_crop(image, group)
        snapshot = _untrusted_snapshot(
            timestamp_seconds=timestamp_seconds,
            actor=actor,
            source_session=source_session,
            stream_epoch=stream_epoch,
            frame_index=frame_index,
            evidence_refs=refs,
        )
        return PublicMeldStructureSnapshotReview(
            snapshot=snapshot,
            geometry=geometry.analysis,
            structural_face_count=None,
            issues=("source_or_public_meld_group_unverified",),
        )

    normalized = normalize_public_meld_crop(image, group)
    state = normalized.analysis.stack_state
    structural_face_count = 3 if state == FLAT else 4 if state == STACKED else None
    structure_ref = f"public_meld_structure:{frame_index}:{state.lower()}"
    merged_refs = tuple(dict.fromkeys((*refs, structure_ref)))

    if structural_face_count is None:
        snapshot = _untrusted_snapshot(
            timestamp_seconds=timestamp_seconds,
            actor=actor,
            source_session=source_session,
            stream_epoch=stream_epoch,
            frame_index=frame_index,
            evidence_refs=merged_refs,
        )
        return PublicMeldStructureSnapshotReview(
            snapshot=snapshot,
            geometry=normalized.analysis,
            structural_face_count=None,
            issues=("public_meld_stack_state_unknown",),
        )

    meld = MeldGroup(
        normalized_bbox=group.normalized_bbox,
        tiles=(None,) * structural_face_count,
        confidence=group.confidence,
        evidence_refs=merged_refs,
    )
    snapshot = MeldSnapshot(
        timestamp_seconds=timestamp_seconds,
        actor=actor,
        groups=(meld,),
        frame=frame_index,
        trusted=True,
        evidence_refs=merged_refs,
        source_session=source_session,
        stream_epoch=stream_epoch,
    )
    return PublicMeldStructureSnapshotReview(
        snapshot=snapshot,
        geometry=normalized.analysis,
        structural_face_count=structural_face_count,
        issues=("geometry_only_unknown_identity",),
    )
