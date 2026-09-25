"""#69: dual-REGION original-video geometry concurrence, DEVELOPMENT ONLY.

One source-adjacent UPPER public raised component disappearing is NOT a
claimed discard: it also happens during ordinary turns. Require a second,
separately reviewed LOWER public-meld onset on the SAME two original frames
before surfacing a human-review candidate. This is a source-scoped join of
two different optical regions, not independent tile identities or 3-channel
river/hand/meld reconstruction. No concealed-hand shadow or replay buttons.
"""
from __future__ import annotations

from dataclasses import dataclass

from workspace.vision.public_meld_adjacent_onset import AdjacentMeldOnsetReview
from workspace.vision.public_raised_tile_withdrawal import (
    RaisedPublicTileWithdrawal,
)

_UPPER_SUCCESS = "PUBLIC_RAISED_TILE_WITHDRAWAL_OPTICAL_CANDIDATE_ONLY"
_LOWER_SUCCESS = "NEW_MELD_VISUALLY_BRACKETED_OWNER_ACTION_PENDING"


@dataclass(frozen=True)
class DualRegionSourceReview:
    status: str
    reason: str
    prior_frame: int | None = None
    first_visible_frame: int | None = None
    lower_face_count: int | None = None

    def to_dict(self) -> dict:
        return {
            "schema_version": "public_dual_region_original_frame_dev_v0_1",
            "development_only": True,
            "status": self.status,
            "reason": self.reason,
            "source_adjacent_frame_delta": (
                self.first_visible_frame - self.prior_frame
                if self.first_visible_frame is not None
                and self.prior_frame is not None else None
            ),
            "lower_face_count": self.lower_face_count,
            "upper_public_shape_identity": "UNKNOWN",
            "claimed_discard_identity": "UNKNOWN",
            "actual_action_kind": "UNKNOWN",
            "actor": "UNKNOWN",
            "hand_count_delta": "UNKNOWN",
            "owner_confirmed_action": False,
            "independent_full_automated_meld_detection": False,
            "independent_triple_observer_verified": False,
            "source_disjoint_blind_test": False,
            "concealed_hand_shading_used": False,
            "replay_button_used": False,
            "safe_for_runtime": False,
            "safe_for_executor": False,
        }


def review_dual_region_original_frame_transition(
    upper: RaisedPublicTileWithdrawal,
    lower: AdjacentMeldOnsetReview,
    *,
    upper_stable_raised_precontrols_source_verified: bool,
    upper_stable_absent_postcontrols_source_verified: bool,
    upper_and_lower_roi_independently_reviewed: bool,
) -> DualRegionSourceReview:
    """Require separate upper withdrawal + lower onset on *identical* frames.

    The caller must separately decode original source frames and confirm
    upper pre/post controls: this function cannot verify the actual pixels
    or lower labels from attestations alone. No positive can be a claim
    without a separate discard ID, hand delta and owner event adjudication.
    """
    if not isinstance(upper, RaisedPublicTileWithdrawal):
        return DualRegionSourceReview("UNKNOWN", "missing_valid_upper_probe")
    if upper.status != _UPPER_SUCCESS or (
        upper.prior_candidates != 1 or upper.after_candidates != 0
    ):
        return DualRegionSourceReview(
            "UNKNOWN", "upper_withdrawal_missing_or_ambiguous"
        )
    if not isinstance(lower, AdjacentMeldOnsetReview):
        return DualRegionSourceReview("UNKNOWN", "lower_source_onset_missing")
    if lower.status != _LOWER_SUCCESS:
        return DualRegionSourceReview(
            "UNKNOWN", "no_separately_reviewed_new_lower_group"
        )
    if (
        upper_stable_raised_precontrols_source_verified is not True
        or upper_stable_absent_postcontrols_source_verified is not True
        or upper_and_lower_roi_independently_reviewed is not True
    ):
        return DualRegionSourceReview(
            "UNKNOWN", "stable_original_source_control_or_region_missing"
        )
    if (
        not upper.source_session
        or not upper.source_sha256
        or type(upper.stream_epoch) is not int
        or upper.stream_epoch < 0
        or (
            upper.source_session, upper.source_sha256, upper.stream_epoch
        ) != (
            lower.source_session, lower.source_sha256, lower.stream_epoch
        )
    ):
        return DualRegionSourceReview(
            "UNKNOWN", "upper_lower_original_source_or_epoch_conflict"
        )
    if lower.screen_side != "lower":
        # Current upper probe covers only the target UI upper action strip.
        # A lower-to-upper claim needs a separate, independently reviewed ROI.
        return DualRegionSourceReview(
            "UNKNOWN", "unsupported_upper_to_upper_or_unknown_side"
        )
    if (
        type(upper.prior_frame) is not int
        or type(upper.after_frame) is not int
        or type(lower.prior_frame) is not int
        or type(lower.first_visible_frame) is not int
        or upper.after_frame != upper.prior_frame + 1
        or lower.first_visible_frame != lower.prior_frame + 1
        or (
            upper.prior_frame, upper.after_frame
        ) != (
            lower.prior_frame, lower.first_visible_frame
        )
    ):
        return DualRegionSourceReview(
            "UNKNOWN", "upper_and_lower_not_same_adjacent_original_frames"
        )
    if (
        not lower.target_track_id
        or len(lower.target_face_ids) not in (3, 4)
        or upper.before_bbox is None
    ):
        return DualRegionSourceReview(
            "UNKNOWN", "public_regions_or_target_faces_not_source_reviewed"
        )
    return DualRegionSourceReview(
        "SYNCHRONIZED_TWO_REGION_APPEARANCE_CANDIDATE_ONLY",
        "stable_upper_withdrawal_and_independently_reviewed_lower_onset_coincide",
        prior_frame=upper.prior_frame,
        first_visible_frame=upper.after_frame,
        lower_face_count=len(lower.target_face_ids),
    )
