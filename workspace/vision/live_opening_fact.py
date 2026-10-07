"""Read-only live opening facts derived from a trusted current-table snapshot.

A live observer cannot reconstruct the simulator's complete hidden GameState.
This module therefore exposes only facts that are directly supported by the
current visible snapshot. In particular, Gold may enter the live state-tracker
boundary only after Runtime Vision has independently trusted the final visible
Gold. Dice, wall position, RNG state and other hidden opening mechanics are
not represented by this contract and cannot be used as fallback inference.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
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
    consume. It deliberately does *not* mean that a complete Environment
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
    other observations remain UNKNOWN. Conversely, no other field is allowed
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
        # selection. A flower here is therefore not a valid final visible Gold.
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
        source_kind="VISIBLE_FINAL_GOLD_MULTIFRAME" if trusted else "UNKNOWN",
        state_tracker_ready=trusted,
        safe_for_environment_state=False,
        safe_for_executor=False,
        selection_inference_used=False,
        issues=tuple(issues),
    )


_GOLD_CONFLICT_ISSUES = frozenset(
    {
        "runtime_gold_component_conflict",
        "runtime_gold_identity_conflict",
        "runtime_gold_fused_identity_conflict",
        "live_gold_flower_forbidden",
        "live_gold_identity_invalid",
    }
)


def _without_runtime_gold_issues(issues: tuple[str, ...]) -> tuple[str, ...]:
    """Drop burst-local Gold failures once a prior visible Gold is authoritative."""
    return tuple(
        issue
        for issue in issues
        if not str(issue).startswith("runtime_gold_")
        and not str(issue).startswith("live_gold_tracker_")
        and issue != "live_gold_carried_forward"
    )


@dataclass
class LiveOpeningTracker:
    """Persist one authoritative visible Gold inside a live capture scope.

    Runtime Vision already performs the within-burst multi-frame identity gate.
    This tracker adds only the missing cross-burst rule:

    * the first trusted nonflower Gold becomes authoritative for that
      ``(source_session, stream_epoch)``;
    * a later missing/temporarily untrusted read may reuse that established
      public fact;
    * a different trusted Gold, a Gold identity conflict, or a forbidden flower
      makes the scope sticky-UNKNOWN until the capture scope changes;
    * changing session or stream epoch resets the fact.

    It never reconstructs a wall index and never imports simulator selection,
    dice or RNG logic.
    """

    minimum_stable_frames: int = 2
    _source_session: str | None = None
    _stream_epoch: int | None = None
    _gold_tile: str | None = None
    _conflicted: bool = False

    def __post_init__(self):
        if isinstance(self.minimum_stable_frames, bool) or not isinstance(
            self.minimum_stable_frames, int
        ) or self.minimum_stable_frames < 1:
            raise ValueError("minimum_stable_frames must be a positive integer")

    def reset(self) -> None:
        self._source_session = None
        self._stream_epoch = None
        self._gold_tile = None
        self._conflicted = False

    def _set_scope(self, snapshot: CurrentTableSnapshot) -> None:
        scope = (snapshot.source_session, snapshot.stream_epoch)
        current = (self._source_session, self._stream_epoch)
        if scope != current:
            self._source_session = snapshot.source_session
            self._stream_epoch = snapshot.stream_epoch
            self._gold_tile = None
            self._conflicted = False

    def _unknown(
        self,
        snapshot: CurrentTableSnapshot,
        raw_fact: LiveOpeningFact,
        issue: str,
    ) -> tuple[CurrentTableSnapshot, LiveOpeningFact]:
        self._gold_tile = None
        self._conflicted = True
        canonical_issues = tuple(
            dict.fromkeys((*_without_runtime_gold_issues(snapshot.adapter_issues), issue))
        )
        canonical = replace(
            snapshot,
            gold_tile=None,
            gold_trusted=False,
            adapter_issues=canonical_issues,
        )
        fact_issues = tuple(dict.fromkeys((*raw_fact.issues, issue)))
        return canonical, LiveOpeningFact(
            timestamp_seconds=snapshot.timestamp_seconds,
            source_session=snapshot.source_session,
            stream_epoch=snapshot.stream_epoch,
            status=LiveOpeningFactStatus.UNKNOWN,
            gold_tile=None,
            gold_trusted=False,
            source_kind="UNKNOWN",
            state_tracker_ready=False,
            safe_for_environment_state=False,
            safe_for_executor=False,
            selection_inference_used=False,
            issues=fact_issues,
        )

    def update(
        self,
        snapshot: CurrentTableSnapshot,
    ) -> tuple[CurrentTableSnapshot, LiveOpeningFact]:
        """Return the canonical live snapshot plus its opening provenance fact."""
        raw_fact = live_opening_fact_from_snapshot(
            snapshot,
            minimum_stable_frames=self.minimum_stable_frames,
        )

        # Invalid scope can never inherit a fact from a previous capture.
        if (
            snapshot.input_source != "runtime_vision"
            or not snapshot.source_session
            or snapshot.stream_epoch < 0
        ):
            self.reset()
            return snapshot, raw_fact

        self._set_scope(snapshot)

        if self._conflicted:
            return self._unknown(
                snapshot,
                raw_fact,
                "live_gold_tracker_conflict_sticky",
            )

        raw_issue_set = set(raw_fact.issues)
        if raw_issue_set.intersection(_GOLD_CONFLICT_ISSUES):
            return self._unknown(
                snapshot,
                raw_fact,
                "live_gold_tracker_observation_conflict",
            )

        if raw_fact.status is LiveOpeningFactStatus.TRUSTED:
            assert raw_fact.gold_tile is not None
            if self._gold_tile is None:
                self._gold_tile = raw_fact.gold_tile
            elif raw_fact.gold_tile != self._gold_tile:
                return self._unknown(
                    snapshot,
                    raw_fact,
                    "live_gold_tracker_identity_conflict",
                )
            return snapshot, raw_fact

        if self._gold_tile is None:
            return snapshot, raw_fact

        # The current burst did not independently re-read Gold, but an earlier
        # burst in the exact same capture scope already established it. Preserve
        # that public fact while retaining non-Gold adapter issues from now.
        canonical = replace(
            snapshot,
            gold_tile=self._gold_tile,
            gold_trusted=True,
            adapter_issues=tuple(
                dict.fromkeys(
                    (
                        *_without_runtime_gold_issues(snapshot.adapter_issues),
                        "live_gold_carried_forward",
                    )
                )
            ),
        )
        fact = LiveOpeningFact(
            timestamp_seconds=snapshot.timestamp_seconds,
            source_session=snapshot.source_session,
            stream_epoch=snapshot.stream_epoch,
            status=LiveOpeningFactStatus.TRUSTED,
            gold_tile=self._gold_tile,
            gold_trusted=True,
            source_kind="VISIBLE_FINAL_GOLD_PERSISTED",
            state_tracker_ready=True,
            safe_for_environment_state=False,
            safe_for_executor=False,
            selection_inference_used=False,
            issues=(),
        )
        return canonical, fact
