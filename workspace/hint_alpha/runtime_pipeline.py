"""Shared read-only Runtime -> snapshot -> structural advisory boundary."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from workspace.vision.live_opening_fact import (
    LiveOpeningFact,
    LiveOpeningTracker,
    live_opening_fact_from_snapshot,
)
from workspace.vision.runtime_public_adapter import current_snapshot_from_runtime
from .current_snapshot_advisor import analyze_snapshot_shanten


_ACTIVE_OPENING_TRACKER: ContextVar[LiveOpeningTracker | None] = ContextVar(
    "hint_alpha_active_opening_tracker",
    default=None,
)


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

    def reset(self) -> None:
        """Forget all persisted opening facts at a trusted boundary."""
        self.opening_tracker.reset()

    @contextmanager
    def bind(self):
        """Bind this pipeline only for the current synchronous UI evaluation."""
        token = _ACTIVE_OPENING_TRACKER.set(self.opening_tracker)
        try:
            yield self
        finally:
            _ACTIVE_OPENING_TRACKER.reset(token)

    def evaluate(self, report, *, captured, experimental=False) -> RuntimeAdvice:
        return evaluate_runtime_report(
            report,
            captured=captured,
            experimental=experimental,
            opening_tracker=self.opening_tracker,
        )
