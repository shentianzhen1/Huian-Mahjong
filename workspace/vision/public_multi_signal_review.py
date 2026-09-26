"""#69: conservative temporal join of independent hand, wall and dual-region cues.

This DEVELOPMENT-ONLY gate is intentionally not an event classifier. Different
optical regions may change on different source frames; an explicitly reviewed
window is required rather than pretending all three changes are simultaneous.
The dual-region source proof is required; hand and wall are separate auxiliary
signals. No private source hashes are emitted to public JSON.
"""
from __future__ import annotations
from dataclasses import dataclass

from workspace.vision.public_dual_region_transition import DualRegionSourceReview
from workspace.vision.public_independent_hand_count import HandCountTransition
from workspace.vision.public_wall_counter import WallCounterTransition


@dataclass(frozen=True)
class MultiSignalReview:
    status: str
    reason: str
    upper_lower_interval: tuple[int, int] | None = None
    hand_delta: int | None = None
    wall_delta: int | None = None

    def to_dict(self) -> dict:
        return {
            "schema_version": "public_multi_signal_dev_v0_1",
            "development_only": True,
            "status": self.status, "reason": self.reason,
            "upper_lower_interval": list(self.upper_lower_interval)
            if self.upper_lower_interval else None,
            "hand_delta": self.hand_delta, "wall_delta": self.wall_delta,
            "actor": "UNKNOWN", "action_kind": "UNKNOWN",
            "incoming_tile": "UNKNOWN", "verified_real_video_event": False,
            "safe_for_runtime": False, "safe_for_executor": False,
        }


def review_multi_signal_window(
    dual: DualRegionSourceReview,
    hand: HandCountTransition,
    wall: WallCounterTransition | None,
    *,
    same_original_source_epoch_independently_verified: bool,
    hand_roi_distinct_from_lower_meld_roi: bool,
    wall_roi_distinct_from_both: bool,
    explicit_review_window: tuple[int, int],
    wall_required: bool = False,
) -> MultiSignalReview:
    """Return a review candidate, never a CHI/PENG/KONG claim.

    Upstream modules currently redact source SHA from their public result
    objects. The caller MUST compare their private source metadata and
    attest the same source/epoch; this gate cannot independently prove it.
    """
    def stop(reason: str) -> MultiSignalReview:
        return MultiSignalReview("UNKNOWN", reason)
    if (not isinstance(dual, DualRegionSourceReview)
            or dual.status != "SYNCHRONIZED_TWO_REGION_APPEARANCE_CANDIDATE_ONLY"
            or type(dual.prior_frame) is not int
            or type(dual.first_visible_frame) is not int
            or dual.prior_frame < 0
            or dual.first_visible_frame <= dual.prior_frame):
        return stop("independent_upper_lower_source_review_missing")
    if (not isinstance(hand, HandCountTransition)
            or hand.status != "INDEPENDENT_HAND_COUNT_DELTA_CANDIDATE_ONLY"
            or hand.interval is None or type(hand.delta) is not int
            or len(hand.interval) != 2
            or any(type(v) is not int for v in hand.interval)):
        return stop("independent_hand_count_transition_missing")
    if type(wall_required) is not bool:
        return stop("invalid_wall_requirement")
    if (same_original_source_epoch_independently_verified is not True
            or hand_roi_distinct_from_lower_meld_roi is not True):
        return stop("source_or_hand_meld_region_independence_missing")
    if (not isinstance(explicit_review_window, tuple)
            or len(explicit_review_window) != 2
            or any(type(n) is not int or n < 0 for n in explicit_review_window)
            or explicit_review_window[0] > explicit_review_window[1]):
        return stop("invalid_explicit_review_window")
    start, end = explicit_review_window
    intervals = ((dual.prior_frame, dual.first_visible_frame), hand.interval)
    if any(a < start or b > end or a >= b for a, b in intervals):
        return stop("required_signal_outside_reviewed_window")
    if hand.delta >= 0:
        # The hand-count decrease is a useful corroboration for a newly
        # exposed group; a draw/re-sort/increase is not that evidence.
        return stop("hand_count_did_not_decrease")
    wall_delta = None
    if wall is not None:
        if (not isinstance(wall, WallCounterTransition)
                or wall.status != "WALL_COUNT_DECREASE_AUXILIARY_ONLY"
                or wall.interval is None or type(wall.delta) is not int
                or wall.delta >= 0
                or len(wall.interval) != 2
                or any(type(v) is not int for v in wall.interval)
                or wall_roi_distinct_from_both is not True):
            return stop("unverified_or_nonindependent_wall_counter")
        a, b = wall.interval
        if a < start or b > end or a >= b:
            return stop("wall_counter_outside_reviewed_window")
        wall_delta = wall.delta
    elif wall_required:
        return stop("required_wall_counter_unavailable")
    return MultiSignalReview(
        "MULTI_SIGNAL_OWNER_REVIEW_CANDIDATE_ONLY",
        "source_scoped_temporal_corroboration_not_verified_action",
        (dual.prior_frame, dual.first_visible_frame), hand.delta, wall_delta,
    )
