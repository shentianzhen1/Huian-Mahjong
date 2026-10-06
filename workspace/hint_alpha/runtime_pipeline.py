"""Shared read-only Runtime -> snapshot -> structural advisory boundary."""
from dataclasses import dataclass

from workspace.vision.runtime_public_adapter import current_snapshot_from_runtime
from .current_snapshot_advisor import analyze_snapshot_shanten


@dataclass(frozen=True)
class RuntimeAdvice:
    snapshot: object
    hint: object
    display_allowed: bool
    safe_for_executor: bool = False


def evaluate_runtime_report(report, *, captured, experimental=False):
    snapshot = current_snapshot_from_runtime(report, timestamp_seconds=captured)
    hint = analyze_snapshot_shanten(snapshot)
    return RuntimeAdvice(
        snapshot, hint,
        hint.allowed and (report.get('safe_for_hint') is True or experimental),
    )
