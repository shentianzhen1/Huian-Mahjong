"""Upgrade a verified count-only HAND_DELTA with independently qualified identities."""
from __future__ import annotations

from workspace.vision.public_hand_identity_delta import HandIdentityDelta, StableHandIdentitySnapshot
from workspace.vision.public_meld_observer_corroboration import SourceBoundObserverFact
from workspace.vision.public_match_reconstruction import ObservationKind, RawObservation


def identity_delta_to_hand_fact(
    before: StableHandIdentitySnapshot,
    after: StableHandIdentitySnapshot,
    delta: HandIdentityDelta,
    *,
    timestamp_seconds: float,
) -> SourceBoundObserverFact | None:
    if delta.status != "IDENTITY_QUALIFIED_HAND_DELTA" or not delta.removed_tiles:
        return None
    if (
        before.source_session != after.source_session
        or before.source_sha256 != after.source_sha256
        or before.stream_epoch != after.stream_epoch
        or before.actor != after.actor
    ):
        return None
    observation = RawObservation(
        timestamp_seconds=float(timestamp_seconds),
        actor=after.actor,
        kind=ObservationKind.HAND_DELTA,
        confidence=min(before.minimum_identity_confidence, after.minimum_identity_confidence),
        evidence_refs=(before.evidence_ref, after.evidence_ref),
        details={
            "removed_tiles": list(delta.removed_tiles),
            "removed_count": len(delta.removed_tiles),
            "hand_delta_identity_observed": True,
            "observer": "identity_qualified_hand_delta_v0_1",
            "source_session": after.source_session,
            "stream_epoch": after.stream_epoch,
            "before_frame": before.frame_index,
            "after_frame": after.frame_index,
        },
    )
    return SourceBoundObserverFact(
        channel="hand", observation=observation,
        source_session=after.source_session, source_sha256=after.source_sha256,
        stream_epoch=after.stream_epoch, frame_index=after.frame_index,
        original_frame_verified=True, stable_source_observation=True,
        independent_public_region_verified=True,
    )
