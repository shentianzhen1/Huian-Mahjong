"""#69: independent source-scoped concealed-hand COUNT transition, development only.

Consumes count observations from an independent hand ROI tracker, never meld
shade or the reviewed discard/meld labels. No action semantics are inferred.
The caller must verify source pixels; this pure gate cannot inspect video.
"""
from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Sequence

_SHA = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class HandCountFrame:
    session: str
    source_sha256: str
    epoch: int
    frame: int
    screen_side: str
    count: int | None
    source_pixels_verified: bool
    independent_hand_roi_verified: bool
    unobscured: bool
    animation_free: bool
    draw_region_separately_counted: bool


@dataclass(frozen=True)
class HandCountTransition:
    status: str
    reason: str
    before_count: int | None = None
    after_count: int | None = None
    delta: int | None = None
    interval: tuple[int, int] | None = None

    def to_dict(self) -> dict:
        return {
            "schema_version": "independent_hand_count_dev_v0_1",
            "development_only": True, "status": self.status,
            "reason": self.reason, "delta": self.delta,
            "source_frame_interval": list(self.interval) if self.interval else None,
            "action_kind": "UNKNOWN", "claimed_tile": "UNKNOWN",
            "independent_meld_corrob": False, "safe_for_runtime": False,
            "safe_for_executor": False,
        }


def review_independent_hand_count(
    frames: Sequence[HandCountFrame], *, transition_after_frame: int,
    stable_frames: int = 3,
) -> HandCountTransition:
    """Two stable plateaus around a known *frame boundary*, not action time.

    Reject intervening gaps, mixed provenance, unstable/occluded frames and
    draw-region ambiguity. A negative count delta alone is NOT CHI/PENG/KONG.
    """
    def stop(reason: str) -> HandCountTransition:
        return HandCountTransition("UNKNOWN", reason)
    if type(stable_frames) is not int or stable_frames < 3:
        return stop("invalid_stability_requirement")
    if type(transition_after_frame) is not int or transition_after_frame < 0:
        return stop("invalid_transition_boundary")
    if len(frames) < 2 * stable_frames:
        return stop("insufficient_consecutive_frames")
    if any(not isinstance(f, HandCountFrame) for f in frames):
        return stop("invalid_frame_type")
    first = frames[0]
    if (not first.session or not _SHA.fullmatch(first.source_sha256)
            or first.screen_side not in ("upper", "lower")
            or type(first.epoch) is not int or first.epoch < 0):
        return stop("invalid_source_scope")
    for i, f in enumerate(frames):
        if ((f.session, f.source_sha256, f.epoch, f.screen_side)
                != (first.session, first.source_sha256, first.epoch, first.screen_side)
                or type(f.frame) is not int or f.frame != first.frame + i):
            return stop("source_epoch_or_frame_discontinuity")
        if (type(f.count) is not int or not 0 <= f.count <= 17
                or any(v is not True for v in (
                    f.source_pixels_verified, f.independent_hand_roi_verified,
                    f.unobscured, f.animation_free,
                    f.draw_region_separately_counted,
                ))):
            return stop("untrusted_or_animated_hand_frame")
    before = [f for f in frames if f.frame < transition_after_frame]
    after = [f for f in frames if f.frame >= transition_after_frame]
    if len(before) < stable_frames or len(after) < stable_frames:
        return stop("missing_stable_pre_or_post_window")
    if len({f.count for f in before}) != 1 or len({f.count for f in after}) != 1:
        return stop("unstable_hand_count_plateau")
    if before[-1].frame + 1 != after[0].frame:
        return stop("transition_window_gap")
    delta = after[0].count - before[-1].count
    if delta == 0:
        return stop("no_independent_hand_count_change")
    return HandCountTransition(
        "INDEPENDENT_HAND_COUNT_DELTA_CANDIDATE_ONLY",
        "source_locked_stable_hand_count_change_not_an_action",
        before[-1].count, after[0].count, delta,
        (before[-1].frame, after[0].frame),
    )
