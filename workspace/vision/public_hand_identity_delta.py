"""Issue #69: fail-closed identity delta between two stable concealed-hand snapshots.

This gate does not classify pixels. It accepts only upstream identity-qualified
snapshots and a separately corroborated semantic count delta. It emits exact
removed tile identities only when multiset subtraction is unique, complete,
same-source, and agrees with the independent count evidence.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
import re

from workspace.vision.public_claim_hand_count_delta import ClaimHandCountDeltaReview

_SHA = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class StableHandIdentitySnapshot:
    source_session: str
    source_sha256: str
    stream_epoch: int
    frame_index: int
    actor: str
    tiles: tuple[str, ...]
    minimum_identity_confidence: float
    identity_threshold: float
    source_frame_verified: bool
    stable_geometry: bool
    complete_concealed_snapshot: bool
    draw_region_separately_accounted: bool
    evidence_ref: str


@dataclass(frozen=True)
class HandIdentityDelta:
    status: str
    reason: str
    removed_tiles: tuple[str, ...] = ()

    def to_dict(self):
        return {
            "schema_version": "public_hand_identity_delta_dev_v0_1",
            "development_only": True,
            "status": self.status,
            "reason": self.reason,
            "removed_tiles": list(self.removed_tiles),
            "formal_promotion_evidence": False,
            "safe_for_runtime": False,
            "safe_for_hint": False,
            "safe_for_executor": False,
        }


def review_hand_identity_delta(before: StableHandIdentitySnapshot,
                               after: StableHandIdentitySnapshot,
                               count_review: ClaimHandCountDeltaReview) -> HandIdentityDelta:
    def stop(reason):
        return HandIdentityDelta("UNKNOWN", reason)
    for row in (before, after):
        if (
            not row.source_session or not _SHA.fullmatch(row.source_sha256)
            or type(row.stream_epoch) is not int or row.stream_epoch < 0
            or type(row.frame_index) is not int or row.frame_index < 0
            or row.actor not in {"player", "opponent"} or not row.tiles
            or not row.evidence_ref
            or isinstance(row.minimum_identity_confidence, bool)
            or isinstance(row.identity_threshold, bool)
            or not 0 <= row.minimum_identity_confidence <= 1
            or not 0 < row.identity_threshold <= 1
        ):
            return stop("invalid_identity_snapshot_contract")
        if not all((row.source_frame_verified, row.stable_geometry,
                    row.complete_concealed_snapshot,
                    row.draw_region_separately_accounted)):
            return stop("identity_snapshot_not_source_verified_stable_complete")
        if row.minimum_identity_confidence < row.identity_threshold:
            return stop("identity_below_frozen_threshold")
    if (
        before.source_session, before.source_sha256, before.stream_epoch, before.actor
    ) != (
        after.source_session, after.source_sha256, after.stream_epoch, after.actor
    ):
        return stop("source_epoch_or_actor_changed")
    if before.frame_index >= after.frame_index or before.evidence_ref == after.evidence_ref:
        return stop("identity_snapshots_not_independent_ordered_evidence")
    if (
        count_review.status != "NEW_MELD_HAND_COUNT_DELTA_CORROBORATED_OWNER_ACTION_PENDING"
        or count_review.actor != before.actor
        or count_review.removed_count not in (2, 3)
    ):
        return stop("independent_semantic_count_delta_not_corroborated")

    b, a = Counter(before.tiles), Counter(after.tiles)
    added = a - b
    removed = b - a
    if added:
        return stop("snapshot_contains_unexplained_added_identity")
    removed_tiles = tuple(sorted(removed.elements()))
    if len(removed_tiles) != count_review.removed_count:
        return stop("identity_delta_disagrees_with_semantic_count_delta")
    if len(before.tiles) - len(after.tiles) != count_review.removed_count:
        return stop("snapshot_lengths_disagree_with_semantic_count_delta")
    return HandIdentityDelta(
        "IDENTITY_QUALIFIED_HAND_DELTA",
        "same_source_complete_multiset_delta_matches_independent_count",
        removed_tiles,
    )
