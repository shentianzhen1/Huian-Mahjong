"""Read-only live opening facts derived from a trusted current-table snapshot.

A live observer cannot reconstruct the simulator's complete hidden GameState.
This module therefore exposes only facts that are directly supported by the
current visible snapshot.  In particular, Gold may enter the live state-tracker
boundary only after Runtime Vision has independently trusted the final visible
Gold.  Dice, wall position, RNG state and other hidden opening mechanics are
not represented by this contract and cannot be used as fallback inference.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from huian._legacy import env

from .current_state_snapshot import CurrentTableSnapshot


class LiveOpeningFactStatus(str, Enum):
    TRUSTED = "TRUSTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class LiveOpeningFact:
    """Minimal immutable opening fact suitable for a future live state tracker.

    ``state_tracker_ready`` means the visible Gold fact itself is safe to
    consume.  It deliberately does *not* mean that a complete Environment
    GameState can be constructed from the observation.
    """

    timestamp_seconds: float
    source_session: str | None
    stream_epoch: int
    status: LiveOpeningFactStatus
    gold_tile: str | None
    gold_trusted: bool
    source_kind: str
    state_tracker_ready: bool
    safe_for_environment_state: bool = False
    safe_for_executor: bool = False
    selection_inference_used: bool = False
    issues: tuple[str, ...] = ()


def live_opening_fact_from_snapshot(
    snapshot: CurrentTableSnapshot,
    *,
    minimum_stable_frames: int = 2,
) -> LiveOpeningFact:
    """Project direct visible Gold into a narrow live state-tracker contract.

    The function is intentionally independent of hand/meld/river completeness.
    A trusted visible Gold can be useful to a public-state tracker even while
    other observations remain UNKNOWN.  Conversely, no other field is allowed
    to infer or repair an untrusted Gold identity.
    """
    if isinstance(minimum_stable_frames, bool) or not isinstance(
        minimum_stable_frames, int
    ) or minimum_stable_frames < 1:
        raise ValueError("minimum_stable_frames must be a positive integer")

    issues: list[str] = []
    if snapshot.input_source != "runtime_vision":
        issues.append("live_opening_requires_runtime_vision")
    if not snapshot.source_session:
        issues.append("live_source_session_missing")
    if snapshot.stream_epoch < 0:
        issues.append("live_stream_epoch_invalid")
    if snapshot.stable_frames < minimum_stable_frames:
        issues.append("live_gold_not_multiframe_stable")
    if not snapshot.gold_trusted:
        issues.append("live_gold_untrusted")
    if snapshot.gold_tile is None:
        issues.append("live_gold_unknown")
    elif snapshot.gold_tile in env.FLOWERS:
        # Target-room 2026-10-07 rule: flowers are excluded before random Gold
        # selection.  A flower here is therefore not a valid final visible Gold.
        issues.append("live_gold_flower_forbidden")
    elif snapshot.gold_tile not in env.BASE_TILES:
        issues.append("live_gold_identity_invalid")

    # A caller must not be able to claim a trusted fact while the Runtime
    # adapter itself recorded a Gold-specific conflict in the same snapshot.
    issues.extend(
        issue
        for issue in snapshot.adapter_issues
        if str(issue).startswith("runtime_gold_")
    )
    issues = list(dict.fromkeys(issues))

    trusted = not issues
    return LiveOpeningFact(
        timestamp_seconds=snapshot.timestamp_seconds,
        source_session=snapshot.source_session,
        stream_epoch=snapshot.stream_epoch,
        status=(
            LiveOpeningFactStatus.TRUSTED
            if trusted
            else LiveOpeningFactStatus.UNKNOWN
        ),
        gold_tile=snapshot.gold_tile if trusted else None,
        gold_trusted=trusted,
        source_kind=(
            "VISIBLE_FINAL_GOLD_MULTIFRAME" if trusted else "UNKNOWN"
        ),
        state_tracker_ready=trusted,
        safe_for_environment_state=False,
        safe_for_executor=False,
        selection_inference_used=False,
        issues=tuple(issues),
    )
