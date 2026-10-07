"""Shared read-only Runtime -> snapshot -> structural advisory boundary."""
from dataclasses import dataclass

from workspace.vision.live_opening_fact import (
    LiveOpeningFact,
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


def evaluate_runtime_report(report, *, captured, experimental=False):
    snapshot = current_snapshot_from_runtime(report, timestamp_seconds=captured)
    opening_fact = live_opening_fact_from_snapshot(snapshot)
    hint = analyze_snapshot_shanten(snapshot)
    return RuntimeAdvice(
        snapshot=snapshot,
        hint=hint,
        display_allowed=bool(
            hint.allowed and (report.get('safe_for_hint') is True or experimental)
        ),
        opening_fact=opening_fact,
        safe_for_executor=False,
    )
