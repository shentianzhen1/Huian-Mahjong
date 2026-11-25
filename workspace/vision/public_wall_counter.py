"""#69: source-locked wall remaining count as a fourth, auxiliary signal.

OCR belongs to an independent on-screen counter ROI. This module does NOT
run OCR, infer the actor, claim a draw, or convert a counter change into a
discard/CHI/PENG/KONG. It deliberately tolerates missing/uncertain OCR by
abstaining. Caller verifies source pixels and the counter ROI.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Sequence

_SHA = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class WallCounterFrame:
    session: str
    source_sha256: str
    epoch: int
    frame: int
    count: int | None
    original_frame_verified: bool
    independent_counter_roi_verified: bool
    counter_visible: bool
    animation_free: bool


@dataclass(frozen=True)
class WallCounterTransition:
    status: str
    reason: str
    before: int | None = None
    after: int | None = None
    delta: int | None = None
    interval: tuple[int, int] | None = None

    def to_dict(self) -> dict:
        return {
            "schema_version": "public_wall_counter_dev_v0_1",
            "development_only": True, "status": self.status,
            "reason": self.reason, "before": self.before,
            "after": self.after, "delta": self.delta,
            "source_frame_interval": list(self.interval) if self.interval else None,
            "actor": "UNKNOWN", "draw_event": "UNKNOWN",
            "action_kind": "UNKNOWN", "safe_for_runtime": False,
            "safe_for_executor": False,
        }


def review_wall_counter_transition(
    frames: Sequence[WallCounterFrame], *, boundary_frame: int,
    stable_frames: int = 3,
) -> WallCounterTransition:
    """Two consecutive stable plateaus; no hardcoded draw/action mapping.

    OCR frames with ambiguous digits, occlusion, animation, source changes or
    implausible counter increases must abstain. Delta magnitude is retained
    only for subsequent independent temporal cross-checking.
    """
    def stop(reason: str) -> WallCounterTransition:
        return WallCounterTransition("UNKNOWN", reason)
    if type(stable_frames) is not int or stable_frames < 3:
        return stop("invalid_stability_requirement")
    if type(boundary_frame) is not int or boundary_frame < 0:
        return stop("invalid_boundary")
    if len(frames) < 2 * stable_frames:
        return stop("insufficient_frames")
    if any(not isinstance(f, WallCounterFrame) for f in frames):
        return stop("invalid_frame_type")
    first = frames[0]
    if (not first.session or not isinstance(first.source_sha256, str)
            or not _SHA.fullmatch(first.source_sha256)
            or type(first.epoch) is not int or first.epoch < 0):
        return stop("invalid_source_scope")
    for i, f in enumerate(frames):
        if ((f.session, f.source_sha256, f.epoch)
                != (first.session, first.source_sha256, first.epoch)
                or type(f.frame) is not int or f.frame != first.frame + i):
            return stop("source_or_frame_discontinuity")
        if (type(f.count) is not int or not 0 <= f.count <= 144
                or any(x is not True for x in (
                    f.original_frame_verified, f.independent_counter_roi_verified,
                    f.counter_visible, f.animation_free,
                ))):
            return stop("untrusted_or_ambiguous_counter_frame")
    before = [f for f in frames if f.frame < boundary_frame]
    after = [f for f in frames if f.frame >= boundary_frame]
    if len(before) < stable_frames or len(after) < stable_frames:
        return stop("missing_stable_pre_or_post_window")
    if len({f.count for f in before}) != 1 or len({f.count for f in after}) != 1:
        return stop("unstable_counter_ocr")
    delta = after[0].count - before[-1].count
    if delta >= 0:
        return stop("no_decrease_or_implausible_counter_increase")
    return WallCounterTransition(
        "WALL_COUNT_DECREASE_AUXILIARY_ONLY",
        "stable_counter_decrease_without_actor_or_action_inference",
        before[-1].count, after[0].count, delta,
        (before[-1].frame, after[0].frame),
    )
