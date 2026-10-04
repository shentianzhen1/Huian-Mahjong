"""Development-only full-frame bridge for public exposed-meld structure.

This composes the existing single-group structure bridge into one actor-scoped
MeldSnapshot containing every verified exposed group visible in the reviewed
public meld region. It exists for Issue #69 offline replay where an actor may
already have one exposed group when a second group appears.

No tile identity or Mahjong action is inferred. UNKNOWN in any supplied group
fails the entire frame closed. An empty group set is trusted only when the
caller independently verified that the actor meld region is empty.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from workspace.vision.public_meld_structure_snapshot_bridge import (
    PublicMeldStructureSnapshotReview,
    review_public_meld_structure_snapshot,
)
from workspace.vision.public_observers import MeldSnapshot
from workspace.vision.public_tile_detector import PublicGeometryCandidate


@dataclass(frozen=True)
class PublicMeldStructureFrameReview:
    snapshot: MeldSnapshot
    group_reviews: tuple[PublicMeldStructureSnapshotReview, ...]
    issues: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "schema_version": "public_meld_structure_frame_bridge_dev_v0_1",
            "development_only": True,
            "snapshot_trusted": self.snapshot.trusted,
            "group_count": len(self.snapshot.groups),
            "structural_face_counts": [
                len(group.tiles) for group in self.snapshot.groups
            ],
            "stack_states": [
                review.geometry.stack_state for review in self.group_reviews
            ],
            "tile_identity": "UNKNOWN",
            "action_kind": "UNKNOWN",
            "issues": list(self.issues),
            "formal_promotion_evidence": False,
            "safe_for_runtime": False,
            "safe_for_hint": False,
            "safe_for_executor": False,
        }


def _snapshot(
    *,
    timestamp_seconds: float,
    actor: str,
    groups: tuple,
    frame_index: int,
    trusted: bool,
    evidence_refs: tuple[str, ...],
    source_session: str,
    stream_epoch: int,
) -> MeldSnapshot:
    return MeldSnapshot(
        timestamp_seconds=timestamp_seconds,
        actor=actor,
        groups=groups,
        frame=frame_index,
        trusted=trusted,
        evidence_refs=evidence_refs,
        source_session=source_session,
        stream_epoch=stream_epoch,
    )


def review_public_meld_structure_frame(
    image: Any,
    groups: Sequence[PublicGeometryCandidate],
    *,
    timestamp_seconds: float,
    actor: str,
    source_session: str,
    stream_epoch: int,
    frame_index: int,
    source_frame_verified: bool,
    public_meld_region_verified: bool,
    empty_meld_set_verified: bool = False,
    evidence_refs: Sequence[str] = (),
) -> PublicMeldStructureFrameReview:
    """Build one complete actor-side meld snapshot from reviewed groups.

    `groups` must contain all detected groups for the actor on this frame, not
    merely the changed group. An empty set is accepted only with the explicit
    `empty_meld_set_verified` guard. Any ambiguous/UNKNOWN group makes the
    whole frame untrusted so an old accepted baseline cannot be erased by a
    transient animation or detector miss.
    """
    if not isinstance(source_session, str) or not source_session:
        raise ValueError("source_session required")
    if isinstance(stream_epoch, bool) or not isinstance(stream_epoch, int) or stream_epoch < 0:
        raise ValueError("stream_epoch must be a nonnegative integer")
    if isinstance(frame_index, bool) or not isinstance(frame_index, int) or frame_index < 0:
        raise ValueError("frame_index must be a nonnegative integer")
    candidates = tuple(groups)
    if any(not isinstance(group, PublicGeometryCandidate) for group in candidates):
        raise ValueError("all groups must be PublicGeometryCandidate")
    refs = tuple(dict.fromkeys(str(ref) for ref in evidence_refs if str(ref)))

    if source_frame_verified is not True or public_meld_region_verified is not True:
        return PublicMeldStructureFrameReview(
            snapshot=_snapshot(
                timestamp_seconds=timestamp_seconds,
                actor=actor,
                groups=(),
                frame_index=frame_index,
                trusted=False,
                evidence_refs=refs,
                source_session=source_session,
                stream_epoch=stream_epoch,
            ),
            group_reviews=(),
            issues=("source_or_public_meld_region_unverified",),
        )

    if not candidates:
        trusted = empty_meld_set_verified is True
        return PublicMeldStructureFrameReview(
            snapshot=_snapshot(
                timestamp_seconds=timestamp_seconds,
                actor=actor,
                groups=(),
                frame_index=frame_index,
                trusted=trusted,
                evidence_refs=refs,
                source_session=source_session,
                stream_epoch=stream_epoch,
            ),
            group_reviews=(),
            issues=(
                "verified_empty_meld_set"
                if trusted else "empty_meld_set_not_independently_verified",
            ),
        )

    ordered = tuple(sorted(
        candidates,
        key=lambda group: (
            group.normalized_bbox[0], group.normalized_bbox[1],
            group.normalized_bbox[2], group.normalized_bbox[3],
        ),
    ))
    reviews = []
    for index, group in enumerate(ordered):
        review = review_public_meld_structure_snapshot(
            image,
            group,
            timestamp_seconds=timestamp_seconds,
            actor=actor,
            source_session=source_session,
            stream_epoch=stream_epoch,
            frame_index=frame_index,
            source_frame_verified=True,
            public_meld_region_verified=True,
            evidence_refs=(*refs, f"public_meld_group:{frame_index}:{index}"),
        )
        reviews.append(review)
        if not review.snapshot.trusted or review.structural_face_count is None:
            return PublicMeldStructureFrameReview(
                snapshot=_snapshot(
                    timestamp_seconds=timestamp_seconds,
                    actor=actor,
                    groups=(),
                    frame_index=frame_index,
                    trusted=False,
                    evidence_refs=refs,
                    source_session=source_session,
                    stream_epoch=stream_epoch,
                ),
                group_reviews=tuple(reviews),
                issues=("one_or_more_meld_groups_ambiguous",),
            )

    meld_groups = tuple(review.snapshot.groups[0] for review in reviews)
    merged_refs = tuple(dict.fromkeys(
        ref
        for review in reviews
        for ref in review.snapshot.evidence_refs
    ))
    return PublicMeldStructureFrameReview(
        snapshot=_snapshot(
            timestamp_seconds=timestamp_seconds,
            actor=actor,
            groups=meld_groups,
            frame_index=frame_index,
            trusted=True,
            evidence_refs=merged_refs,
            source_session=source_session,
            stream_epoch=stream_epoch,
        ),
        group_reviews=tuple(reviews),
        issues=("complete_actor_meld_structure_snapshot",),
    )
