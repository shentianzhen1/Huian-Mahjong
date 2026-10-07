"""Shared read-only Runtime -> snapshot -> structural advisory boundary."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from numbers import Integral

from workspace.vision.live_opening_fact import (
    LiveOpeningFact,
    LiveOpeningTracker,
    live_opening_fact_from_snapshot,
)
from workspace.vision.runtime_public_adapter import current_snapshot_from_runtime
from .current_snapshot_advisor import analyze_snapshot_shanten
from .live_snapshot_stability import LiveSnapshotStability


_ACTIVE_OPENING_TRACKER: ContextVar[LiveOpeningTracker | None] = ContextVar(
    "hint_alpha_active_opening_tracker",
    default=None,
)
_ACTIVE_STABILITY_TRACKER: ContextVar[LiveSnapshotStability | None] = ContextVar(
    "hint_alpha_active_stability_tracker", default=None,
)


def confirmed_public_hand_boundary(previous_hand, observation, *, minimum_votes=2):
    """Return True only for an initial or sequentially confirmed public hand.

    Runtime ``stream_epoch`` is a capture generation and can span multiple
    Mahjong hands, so it cannot reset Gold by itself. PublicState hand number is
    the observable boundary, but a regression or jump must not clear a conflict.
    With an existing hand, only N -> N+1 is accepted. With no prior hand, an
    in-range consensus establishes the initial hand boundary.
    """
    if isinstance(minimum_votes, bool) or not isinstance(minimum_votes, Integral):
        raise ValueError("minimum_votes must be an integer")
    if minimum_votes < 1:
        raise ValueError("minimum_votes must be >= 1")

    hand_number = getattr(observation, "hand_number", None)
    hand_votes = getattr(observation, "hand_votes", 0)
    if (
        isinstance(hand_number, bool)
        or not isinstance(hand_number, Integral)
        or not 1 <= hand_number <= 8
    ):
        return False
    if (
        isinstance(hand_votes, bool)
        or not isinstance(hand_votes, Integral)
        or hand_votes < minimum_votes
    ):
        return False

    if previous_hand is None:
        return True
    if isinstance(previous_hand, bool) or not isinstance(previous_hand, Integral):
        return False
    return hand_number == previous_hand + 1


@dataclass(frozen=True)
class RuntimeAdvice:
    snapshot: object
    hint: object
    display_allowed: bool
    opening_fact: LiveOpeningFact
    safe_for_executor: bool = False


def evaluate_runtime_report(
    report,
    *,
    captured,
    experimental=False,
    opening_tracker: LiveOpeningTracker | None = None,
    stability_tracker: LiveSnapshotStability | None = None,
):
    """Evaluate one Runtime burst without enabling any action path.

    ``opening_tracker`` is explicit for tests and non-UI callers. A live UI may
    instead bind one tracker to the current synchronous evaluation context via
    :meth:`RuntimeAdvicePipeline.bind`. With neither form present the function
    stays stateless, preserving isolated diagnostics and replay behavior.
    """
    tracker = opening_tracker
    if tracker is None:
        tracker = _ACTIVE_OPENING_TRACKER.get()

    snapshot = current_snapshot_from_runtime(report, timestamp_seconds=captured)
    if tracker is None:
        opening_fact = live_opening_fact_from_snapshot(snapshot)
    else:
        snapshot, opening_fact = tracker.update(snapshot)
    stability_tracker = stability_tracker or _ACTIVE_STABILITY_TRACKER.get()
    if stability_tracker is not None:
        snapshot = stability_tracker.update(snapshot, report)
    hint = analyze_snapshot_shanten(snapshot)
    return RuntimeAdvice(
        snapshot=snapshot,
        hint=hint,
        display_allowed=bool(
            hint.allowed and (report.get("safe_for_hint") is True or experimental)
        ),
        opening_fact=opening_fact,
        safe_for_executor=False,
    )


@dataclass
class RuntimeAdvicePipeline:
    """Long-lived advisory session with explicitly resettable Gold memory."""

    opening_tracker: LiveOpeningTracker = field(default_factory=LiveOpeningTracker)
    stability_tracker: LiveSnapshotStability | None = None

    def reset(self) -> None:
        """Forget all persisted opening facts at a trusted boundary."""
        self.opening_tracker.reset()
        if self.stability_tracker is not None:
            self.stability_tracker.reset()

    @contextmanager
    def bind(self):
        """Bind this pipeline only for the current synchronous UI evaluation."""
        token = _ACTIVE_OPENING_TRACKER.set(self.opening_tracker)
        stability_token = _ACTIVE_STABILITY_TRACKER.set(self.stability_tracker)
        try:
            yield self
        finally:
            _ACTIVE_STABILITY_TRACKER.reset(stability_token)
            _ACTIVE_OPENING_TRACKER.reset(token)

    def evaluate(self, report, *, captured, experimental=False) -> RuntimeAdvice:
        return evaluate_runtime_report(
            report,
            captured=captured,
            experimental=experimental,
            opening_tracker=self.opening_tracker,
            stability_tracker=self.stability_tracker,
        )
