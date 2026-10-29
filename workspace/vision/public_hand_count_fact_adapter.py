"""Issue #69: bridge a verified semantic hand-count drop into HAND_DELTA.

This adapter is deliberately narrow. It converts ONLY a successful
ClaimHandCountDeltaReview plus its original source-scoped before/after
samples into one SourceBoundObserverFact(channel="hand"). It never invents
concealed identities, never uses hand shadows, and never marks an action
complete by itself.

The resulting HAND_DELTA uses removed_count only. Exact removed tile IDs
remain unknown unless a separate player-hand identity observer provides them.
"""
from __future__ import annotations

from workspace.vision.public_claim_hand_count_delta import (
    ClaimHandCountDeltaReview,
    SourceScopedStableHandCount,
)
from workspace.vision.public_match_reconstruction import ObservationKind, RawObservation
from workspace.vision.public_meld_observer_corroboration import SourceBoundObserverFact


def hand_count_review_to_source_fact(
    before: SourceScopedStableHandCount,
    after: SourceScopedStableHandCount,
    review: ClaimHandCountDeltaReview,
    *,
    timestamp_seconds: float,
) -> SourceBoundObserverFact | None:
    """Return a source-bound HAND_DELTA only for a successful same-source review."""
    if (
        review.status
        != "NEW_MELD_HAND_COUNT_DELTA_CORROBORATED_OWNER_ACTION_PENDING"
        or review.removed_count not in (2, 3)
        or review.actor != after.actor
        or review.before_frame != before.frame_index
        or review.after_frame != after.frame_index
        or review.before_count != before.semantic_concealed_count
        or review.after_count != after.semantic_concealed_count
        or review.new_meld_face_count not in (3, 4)
        or review.removed_count != review.new_meld_face_count - 1
    ):
        return None
    if (
        before.source_session != after.source_session
        or before.source_sha256 != after.source_sha256
        or before.stream_epoch != after.stream_epoch
        or before.actor != after.actor
        or not before.evidence_ref
        or not after.evidence_ref
        or before.evidence_ref == after.evidence_ref
    ):
        return None
    if isinstance(timestamp_seconds, bool) or not isinstance(
        timestamp_seconds, (int, float)
    ) or timestamp_seconds < 0:
        raise ValueError("timestamp_seconds must be a nonnegative number")

    refs = (before.evidence_ref, after.evidence_ref)
    observation = RawObservation(
        timestamp_seconds=float(timestamp_seconds),
        actor=after.actor,
        kind=ObservationKind.HAND_DELTA,
        confidence=1.0,
        evidence_refs=refs,
        details={
            "removed_count": review.removed_count,
            "hand_delta_identity_observed": False,
            "observer": "semantic_hand_count_delta_v0_1",
            "source_session": after.source_session,
            "stream_epoch": after.stream_epoch,
            "before_frame": before.frame_index,
            "after_frame": after.frame_index,
            "new_meld_face_count": review.new_meld_face_count,
            "concealed_hand_shadow_used": False,
        },
    )
    return SourceBoundObserverFact(
        channel="hand",
        observation=observation,
        source_session=after.source_session,
        source_sha256=after.source_sha256,
        stream_epoch=after.stream_epoch,
        frame_index=after.frame_index,
        original_frame_verified=True,
        stable_source_observation=True,
        independent_public_region_verified=True,
    )
