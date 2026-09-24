"""Source-scoped development observer for DELAYED visible meld-face shading.

An acquired face may darken some time AFTER the actual CHI/PENG/KONG and
after the exposed meld becomes visible. A darkening transition is therefore
neither the action timestamp nor evidence that a new action occurred.

Inputs must come from separately SHA-verified, REVIEWED public-meld frames;
this pure module does not perform source verification or infer tile IDs.
It is intentionally disconnected from Runtime, Ledger, Hint and Executor.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Sequence

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_GROUP_STATES = frozenset({"newly_observed", "pre_existing", "unknown"})


@dataclass(frozen=True)
class SourceScopedShadeFrame:
    source_session: str
    source_sha256: str
    stream_epoch: int
    meld_track_id: str
    frame_index: int
    shadow_index: int | None
    reviewed_public_meld: bool
    regular_three_faces: bool
    exact_source_frame_verified: bool


@dataclass(frozen=True)
class DelayedShadeReview:
    status: str
    shadow_index: int | None
    meld_first_observed_frame: int | None
    shade_first_observed_frame: int | None
    observed_lag_frames: int | None
    observed_lag_seconds: float | None
    issues: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "schema_version": "public_meld_delayed_shade_review_v0_1",
            "development_only": True,
            "status": self.status,
            "shadow_index": self.shadow_index,
            "meld_first_observed_frame": self.meld_first_observed_frame,
            "shade_first_observed_frame": self.shade_first_observed_frame,
            # This is NOT a CHI/PENG/KONG-to-shade action delay:
            "observed_lag_frames_from_first_meld_observation":
                self.observed_lag_frames,
            "observed_lag_seconds_from_first_meld_observation":
                self.observed_lag_seconds,
            "actual_action_frame": None,
            "actual_action_to_shade_delay": None,
            "independently_verified_preceding_discard": False,
            "incoming_tile_id": "UNKNOWN",
            "actor": "UNKNOWN",
            "turn_actor": "UNKNOWN",
            "action_kind": "UNKNOWN",
            "formal_promotion_evidence": False,
            "safe_for_runtime": False,
            "safe_for_executor": False,
            "issues": list(self.issues),
        }


def _unknown(reason: str) -> DelayedShadeReview:
    return DelayedShadeReview(
        "UNKNOWN", None, None, None, None, None, (reason,),
    )


def review_delayed_shade(
    frames: Sequence[SourceScopedShadeFrame],
    *,
    group_history: str = "unknown",
    minimum_stable_observations: int = 2,
    max_gap_frames: int = 1,
    verified_video_fps: float | None = None,
) -> DelayedShadeReview:
    """Find first persistently shaded slot, without deriving an action event.

    group_history must come from independent *earlier* group-geometry review.
    'newly_observed' means first observed here, NOT proven newly claimed.
    'pre_existing' means already visible before this sequence, so any later
    shade onset is specifically NOT new-meld/action evidence.

    Default stability needs >=2 adjacent SOURCE frames. Downsampled video
    callers must explicitly set the largest validated observation spacing;
    a stream gap beyond that spacing resets the shade streak. The time span
    is measured relative to FIRST OBSERVED MELD FRAME only, NEVER a claimed
    action frame. No hardcoded game animation delay or timeout.
    """
    if group_history not in _GROUP_STATES:
        raise ValueError("group_history must be independently classified or unknown")
    if (
        type(minimum_stable_observations) is not int
        or minimum_stable_observations < 2
        or type(max_gap_frames) is not int
        or max_gap_frames < 1
    ):
        raise ValueError("temporal stability requires >=2 observations and positive gap")
    if (
        verified_video_fps is not None
        and (
            isinstance(verified_video_fps, bool)
            or not isinstance(verified_video_fps, (int, float))
            or not (0 < verified_video_fps <= 240)
        )
    ):
        raise ValueError("verified source video FPS is invalid")
    if not frames:
        return _unknown("no_source_frames")
    first = frames[0]
    if (
        not first.source_session or not first.meld_track_id
        or not _SHA256.fullmatch(first.source_sha256)
        or type(first.stream_epoch) is not int or first.stream_epoch < 0
    ):
        return _unknown("invalid_or_missing_source_provenance")
    binding = (
        first.source_session, first.source_sha256,
        first.stream_epoch, first.meld_track_id,
    )
    last_frame = -1
    for frame in frames:
        if (
            (
                frame.source_session, frame.source_sha256,
                frame.stream_epoch, frame.meld_track_id,
            ) != binding
            or type(frame.frame_index) is not int
            or frame.frame_index <= last_frame
        ):
            return _unknown("source_epoch_track_or_frame_continuity_failure")
        last_frame = frame.frame_index
        if (
            frame.reviewed_public_meld is not True
            or frame.regular_three_faces is not True
            or frame.exact_source_frame_verified is not True
        ):
            return _unknown("unverified_or_non_meld_frame")
        if (
            frame.shadow_index is not None
            and (
                type(frame.shadow_index) is not int
                or frame.shadow_index not in (0, 1, 2)
            )
        ):
            return _unknown("invalid_shaded_face_position")

    if first.shadow_index is not None:
        # There is no source-verifiable earlier unshaded baseline: left censor.
        return DelayedShadeReview(
            "SHADE_ALREADY_PRESENT", None, first.frame_index, None,
            None, None, ("no_observed_unshaded_baseline",),
        )

    earliest: tuple[int, int] | None = None
    accepted_positions: set[int] = set()
    streak_position: int | None = None
    streak_start: int | None = None
    streak_length = 0
    previous_frame = first.frame_index
    for observation in frames[1:]:
        position = observation.shadow_index
        if (
            position is None
            or observation.frame_index - previous_frame > max_gap_frames
        ):
            streak_position = None
            streak_start = None
            streak_length = 0
        if position is not None:
            if position != streak_position:
                streak_position = position
                streak_start = observation.frame_index
                streak_length = 1
            else:
                streak_length += 1
            if streak_length >= minimum_stable_observations:
                accepted_positions.add(position)
                if earliest is None:
                    assert streak_start is not None
                    earliest = (position, streak_start)
        previous_frame = observation.frame_index

    if len(accepted_positions) > 1:
        return _unknown("conflicting_stable_shaded_face_positions")
    if earliest is None:
        return DelayedShadeReview(
            "PENDING_OR_ABSTAINED", None, first.frame_index, None,
            None, None, ("no_stable_delayed_shade_after_unshaded_baseline",),
        )
    index, shade_frame = earliest
    lag_frames = shade_frame - first.frame_index
    lag_seconds = (
        round(lag_frames / verified_video_fps, 4)
        if verified_video_fps is not None else None
    )
    if group_history == "pre_existing":
        status = "PRE_EXISTING_GROUP_SHADE_CHANGE_UNATTRIBUTED"
        reason = "group_existed_before_baseline_not_a_new_action"
    elif group_history == "newly_observed":
        status = "DELAYED_SHADE_AFTER_MELD_APPEARANCE"
        reason = "first_group_visibility_is_not_verified_action_time"
    else:
        status = "DELAYED_SHADE_GROUP_HISTORY_UNKNOWN"
        reason = "not_proven_whether_meld_was_new_or_already_present"
    return DelayedShadeReview(
        status, index, first.frame_index, shade_frame,
        lag_frames, lag_seconds,
        (reason, "discard_and_hand_delta_must_be_independently_correlated"),
    )
