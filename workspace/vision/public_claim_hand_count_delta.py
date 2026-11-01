"""Issue #69: source-scoped concealed HAND COUNT delta around a NEW public meld.

This module intentionally does NOT use concealed-hand shading or raw slot
brightness. It accepts only semantic concealed counts from an upstream
geometry/draw tracker after that tracker has marked the frame trusted and
stable. A positive is still just a development consistency fact.

For a genuinely NEW 3-face claimed meld, exactly two concealed tiles must be
consumed before the claimant's mandatory follow-up discard. For a genuinely
NEW 4-face claimed meld, exactly three concealed tiles are consumed. The
caller must independently bracket the new-meld onset and attest that no draw,
discard, resort, replacement draw, hand occlusion or hand-ROI reset is folded
into the two count samples. Added-kong (3->4 existing meld) is excluded.

No Rules/AI/Hint/Runtime/Executor integration.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

_SHA = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class SourceScopedStableHandCount:
    source_session: str
    source_sha256: str
    stream_epoch: int
    frame_index: int
    actor: str
    semantic_concealed_count: int
    tracker_state: str
    tracker_trusted: bool
    tracker_stable: bool
    hand_geometry_region_verified: bool
    source_frame_verified: bool
    draw_event_in_sample: bool = False
    discard_event_in_sample: bool = False
    hand_resort_or_occlusion_in_sample: bool = False
    geometry_baseline_reset_in_sample: bool = False
    evidence_ref: str = ""


@dataclass(frozen=True)
class ClaimHandCountDeltaReview:
    status: str
    reason: str
    actor: str | None = None
    before_frame: int | None = None
    after_frame: int | None = None
    before_count: int | None = None
    after_count: int | None = None
    removed_count: int | None = None
    new_meld_face_count: int | None = None

    def to_dict(self) -> dict:
        return {
            "schema_version": "public_claim_hand_count_delta_dev_v0_1",
            "development_only": True,
            "status": self.status,
            "reason": self.reason,
            "actor": self.actor or "UNKNOWN",
            "before_frame": self.before_frame,
            "after_frame": self.after_frame,
            "before_count": self.before_count,
            "after_count": self.after_count,
            "removed_count": self.removed_count,
            "new_meld_face_count": self.new_meld_face_count,
            "concealed_hand_shadow_used": False,
            "semantic_count_only": True,
            "added_kong_supported": False,
            "claim_action_kind": "UNKNOWN",
            "claimed_tile": "UNKNOWN",
            "requires_independent_discard_and_meld_onset": True,
            "requires_no_intervening_draw_discard_resort": True,
            "owner_confirmed_action": False,
            "formal_promotion_evidence": False,
            "safe_for_runtime": False,
            "safe_for_executor": False,
        }


def _unknown(reason: str) -> ClaimHandCountDeltaReview:
    return ClaimHandCountDeltaReview("UNKNOWN", reason)


def review_new_meld_hand_count_delta(
    before: SourceScopedStableHandCount,
    after: SourceScopedStableHandCount,
    *,
    new_meld_first_visible_frame: int,
    new_meld_face_count: int,
    pre_sample_brackets_onset: bool,
    post_sample_before_followup_discard: bool,
    independent_public_meld_onset_verified: bool,
) -> ClaimHandCountDeltaReview:
    """Verify only the structural count delta for a separately proven NEW meld.

    No fixed timing window is guessed here. The caller supplies source-frame
    bracket truth from the actual video/replay and must independently verify
    the public meld onset. A 3-face NEW group expects -2 concealed tiles;
    a 4-face NEW group expects -3. This cannot classify CHI vs PENG, and it
    cannot classify any form of added Kong.
    """
    frames = (before, after)
    for item in frames:
        if (
            not isinstance(item.source_session, str) or not item.source_session
            or not isinstance(item.source_sha256, str)
            or not _SHA.fullmatch(item.source_sha256)
            or type(item.stream_epoch) is not int or item.stream_epoch < 0
            or type(item.frame_index) is not int or item.frame_index < 0
            or item.actor not in {"player", "opponent"}
            or type(item.semantic_concealed_count) is not int
            or item.semantic_concealed_count < 0
            or not isinstance(item.tracker_state, str) or not item.tracker_state
            or not isinstance(item.evidence_ref, str) or not item.evidence_ref
        ):
            return _unknown("invalid_source_or_semantic_count_contract")
        if any(v is not True for v in (
            item.tracker_trusted,
            item.tracker_stable,
            item.hand_geometry_region_verified,
            item.source_frame_verified,
        )):
            return _unknown("hand_count_not_trusted_stable_or_source_verified")
        if any(v is not False for v in (
            item.draw_event_in_sample,
            item.discard_event_in_sample,
            item.hand_resort_or_occlusion_in_sample,
            item.geometry_baseline_reset_in_sample,
        )):
            return _unknown("sample_contaminated_by_draw_discard_resort_or_reset")
        if item.tracker_state != "STABLE_HAND":
            return _unknown("semantic_count_not_from_stable_hand_state")

    if (
        before.source_session != after.source_session
        or before.source_sha256 != after.source_sha256
        or before.stream_epoch != after.stream_epoch
        or before.actor != after.actor
    ):
        return _unknown("source_epoch_or_actor_changed")

    if (
        type(new_meld_first_visible_frame) is not int
        or new_meld_first_visible_frame < 0
        or new_meld_face_count not in (3, 4)
        or pre_sample_brackets_onset is not True
        or post_sample_before_followup_discard is not True
        or independent_public_meld_onset_verified is not True
    ):
        return _unknown("new_meld_onset_or_source_bracket_unverified")

    if not (
        before.frame_index < new_meld_first_visible_frame <= after.frame_index
        and before.frame_index < after.frame_index
    ):
        return _unknown("hand_count_samples_do_not_bracket_new_meld_onset")

    if before.evidence_ref == after.evidence_ref:
        return _unknown("before_and_after_counts_share_same_evidence_reference")

    removed = before.semantic_concealed_count - after.semantic_concealed_count
    expected = new_meld_face_count - 1
    if removed != expected:
        return ClaimHandCountDeltaReview(
            "CONFLICT",
            "semantic_concealed_count_drop_does_not_match_new_meld_structure",
            actor=after.actor,
            before_frame=before.frame_index,
            after_frame=after.frame_index,
            before_count=before.semantic_concealed_count,
            after_count=after.semantic_concealed_count,
            removed_count=removed,
            new_meld_face_count=new_meld_face_count,
        )

    return ClaimHandCountDeltaReview(
        "NEW_MELD_HAND_COUNT_DELTA_CORROBORATED_OWNER_ACTION_PENDING",
        "stable_semantic_count_drop_matches_new_meld_consumed_tile_count",
        actor=after.actor,
        before_frame=before.frame_index,
        after_frame=after.frame_index,
        before_count=before.semantic_concealed_count,
        after_count=after.semantic_concealed_count,
        removed_count=removed,
        new_meld_face_count=new_meld_face_count,
    )
