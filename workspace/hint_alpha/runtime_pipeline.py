"""Shared read-only Runtime -> snapshot -> structural advisory boundary."""
from dataclasses import dataclass, field

from workspace.vision.live_opening_fact import (
    LiveOpeningFact,
    LiveOpeningTracker,
    live_opening_fact_from_snapshot,
)
from workspace.vision.runtime_public_adapter import current_snapshot_from_runtime
from .current_snapshot_advisor import analyze_snapshot_shanten


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

    Passing ``opening_tracker`` opts into same-session cross-burst Gold
    persistence. Omitting it preserves the original stateless behavior used by
    isolated diagnostics and tests.
    """
    snapshot = current_snapshot_from_runtime(report, timestamp_seconds=captured)
    if opening_tracker is None:
        opening_fact = live_opening_fact_from_snapshot(snapshot)
    else:
        snapshot, opening_fact = opening_tracker.update(snapshot)
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
    """Long-lived advisory session with capture-scoped opening fact memory."""

    opening_tracker: LiveOpeningTracker = field(default_factory=LiveOpeningTracker)

    def reset(self) -> None:
        self.opening_tracker.reset()

    def evaluate(self, report, *, captured, experimental=False) -> RuntimeAdvice:
        return evaluate_runtime_report(
            report,
            captured=captured,
            experimental=experimental,
            opening_tracker=self.opening_tracker,
        )
