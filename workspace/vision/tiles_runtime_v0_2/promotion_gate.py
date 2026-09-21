"""Machine-checkable promotion gate for Runtime Vision V0.2.

This gate decides only whether Runtime Vision V0.2 may be called the project's
formal read-only observation baseline. It never enables Executor and it never
turns failed/unknown evidence into a pass.

The thresholds are frozen before a new independent holdout is evaluated. If a
threshold must change, change the contract first and use a fresh untouched
holdout afterwards.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PromotionThresholds:
    independent_source_sessions_min: int = 8

    geometry_component_precision_min: float = 0.98
    geometry_component_recall_min: float = 0.98
    geometry_hand_count_exact_min: float = 0.95
    geometry_runtime_region_errors_max: int = 0

    tile_standard_classes_required: int = 34
    tile_accepted_accuracy_min: float = 0.99
    tile_accepted_labels_min: int = 100

    draw_events_min: int = 30
    draw_event_precision_min: float = 0.98
    draw_event_recall_min: float = 0.98
    draw_duplicate_events_max: int = 0

    public_state_score_points_min: int = 64
    public_state_score_pair_accuracy_min: float = 0.99
    public_state_status_points_min: int = 40
    public_state_remaining_tiles_accuracy_min: float = 0.98
    public_state_hand_index_accuracy_min: float = 0.98

    gold_sessions_min: int = 8
    gold_session_majority_accuracy_min: float = 1.0

    stress_cases_min: int = 20
    stress_unsafe_acceptances_max: int = 0


DEFAULT_THRESHOLDS = PromotionThresholds()


def _metric(report: dict[str, Any], path: str) -> Any:
    value: Any = report
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _check(
    checks: list[dict[str, Any]],
    *,
    name: str,
    actual: Any,
    op: str,
    threshold: Any,
) -> None:
    if actual is None:
        passed = False
        reason = "missing_metric"
    elif op == ">=":
        passed = actual >= threshold
        reason = "passed" if passed else "below_threshold"
    elif op == "<=":
        passed = actual <= threshold
        reason = "passed" if passed else "above_threshold"
    elif op == "==":
        passed = actual == threshold
        reason = "passed" if passed else "not_equal"
    else:
        raise ValueError(f"Unsupported operator: {op}")
    checks.append({
        "name": name,
        "actual": actual,
        "operator": op,
        "threshold": threshold,
        "passed": passed,
        "reason": reason,
    })


def evaluate_promotion_bundle(
    bundle: dict[str, Any],
    thresholds: PromotionThresholds = DEFAULT_THRESHOLDS,
) -> dict[str, Any]:
    """Evaluate a frozen independent-batch evidence bundle.

    Required top-level sections:
      provenance, geometry, tile_identity, draw_temporal, public_state, gold, stress.

    Missing evidence fails closed. This function does not infer values from older
    development reports.
    """
    checks: list[dict[str, Any]] = []

    _check(
        checks,
        name="independent_batch",
        actual=_metric(bundle, "provenance.independent_batch"),
        op="==",
        threshold=True,
    )
    _check(
        checks,
        name="holdout_locked_before_evaluation",
        actual=_metric(bundle, "provenance.holdout_locked_before_evaluation"),
        op="==",
        threshold=True,
    )
    _check(
        checks,
        name="tuning_after_lock",
        actual=_metric(bundle, "provenance.tuning_after_lock"),
        op="==",
        threshold=False,
    )
    _check(
        checks,
        name="source_sessions",
        actual=_metric(bundle, "provenance.source_sessions"),
        op=">=",
        threshold=thresholds.independent_source_sessions_min,
    )

    _check(
        checks,
        name="geometry_component_precision",
        actual=_metric(bundle, "geometry.component_precision"),
        op=">=",
        threshold=thresholds.geometry_component_precision_min,
    )
    _check(
        checks,
        name="geometry_component_recall",
        actual=_metric(bundle, "geometry.component_recall"),
        op=">=",
        threshold=thresholds.geometry_component_recall_min,
    )
    _check(
        checks,
        name="geometry_hand_count_exact",
        actual=_metric(bundle, "geometry.hand_count_exact_match_rate"),
        op=">=",
        threshold=thresholds.geometry_hand_count_exact_min,
    )
    _check(
        checks,
        name="geometry_runtime_region_errors",
        actual=_metric(bundle, "geometry.runtime_region_errors"),
        op="<=",
        threshold=thresholds.geometry_runtime_region_errors_max,
    )

    _check(
        checks,
        name="tile_standard_classes_covered",
        actual=_metric(bundle, "tile_identity.standard_classes_covered"),
        op=">=",
        threshold=thresholds.tile_standard_classes_required,
    )
    _check(
        checks,
        name="tile_standard_classes_missing",
        actual=_metric(bundle, "tile_identity.standard_classes_missing"),
        op="==",
        threshold=0,
    )
    _check(
        checks,
        name="tile_accepted_accuracy",
        actual=_metric(bundle, "tile_identity.accepted_accuracy"),
        op=">=",
        threshold=thresholds.tile_accepted_accuracy_min,
    )
    _check(
        checks,
        name="tile_accepted_labels",
        actual=_metric(bundle, "tile_identity.accepted_labels"),
        op=">=",
        threshold=thresholds.tile_accepted_labels_min,
    )

    _check(
        checks,
        name="draw_events",
        actual=_metric(bundle, "draw_temporal.events"),
        op=">=",
        threshold=thresholds.draw_events_min,
    )
    _check(
        checks,
        name="draw_event_precision",
        actual=_metric(bundle, "draw_temporal.precision"),
        op=">=",
        threshold=thresholds.draw_event_precision_min,
    )
    _check(
        checks,
        name="draw_event_recall",
        actual=_metric(bundle, "draw_temporal.recall"),
        op=">=",
        threshold=thresholds.draw_event_recall_min,
    )
    _check(
        checks,
        name="draw_duplicate_events",
        actual=_metric(bundle, "draw_temporal.duplicate_events"),
        op="<=",
        threshold=thresholds.draw_duplicate_events_max,
    )

    _check(
        checks,
        name="public_state_score_points",
        actual=_metric(bundle, "public_state.score_points"),
        op=">=",
        threshold=thresholds.public_state_score_points_min,
    )
    _check(
        checks,
        name="public_state_score_pair_accuracy",
        actual=_metric(bundle, "public_state.score_pair_accuracy"),
        op=">=",
        threshold=thresholds.public_state_score_pair_accuracy_min,
    )
    _check(
        checks,
        name="public_state_status_points",
        actual=_metric(bundle, "public_state.status_points"),
        op=">=",
        threshold=thresholds.public_state_status_points_min,
    )
    _check(
        checks,
        name="public_state_remaining_tiles_accuracy",
        actual=_metric(bundle, "public_state.remaining_tiles_accuracy"),
        op=">=",
        threshold=thresholds.public_state_remaining_tiles_accuracy_min,
    )
    _check(
        checks,
        name="public_state_hand_index_accuracy",
        actual=_metric(bundle, "public_state.hand_index_accuracy"),
        op=">=",
        threshold=thresholds.public_state_hand_index_accuracy_min,
    )

    _check(
        checks,
        name="gold_sessions",
        actual=_metric(bundle, "gold.sessions"),
        op=">=",
        threshold=thresholds.gold_sessions_min,
    )
    _check(
        checks,
        name="gold_session_majority_accuracy",
        actual=_metric(bundle, "gold.session_majority_accuracy"),
        op=">=",
        threshold=thresholds.gold_session_majority_accuracy_min,
    )

    _check(
        checks,
        name="stress_cases",
        actual=_metric(bundle, "stress.cases"),
        op=">=",
        threshold=thresholds.stress_cases_min,
    )
    _check(
        checks,
        name="stress_unsafe_acceptances",
        actual=_metric(bundle, "stress.unsafe_acceptances"),
        op="<=",
        threshold=thresholds.stress_unsafe_acceptances_max,
    )

    _check(
        checks,
        name="safe_for_executor_remains_false",
        actual=_metric(bundle, "policy.safe_for_executor"),
        op="==",
        threshold=False,
    )

    failed = [item for item in checks if not item["passed"]]
    return {
        "schema_version": "vision_runtime_v0_2_promotion_gate_v0_1",
        "thresholds": asdict(thresholds),
        "checks": checks,
        "passed": not failed,
        "failed_checks": [item["name"] for item in failed],
        "formal_runtime_baseline_ready": not failed,
        "executor_ready": False,
        "policy": (
            "A pass promotes only the read-only Runtime Vision baseline. "
            "Executor requires a separate post-action safety gate."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate a frozen independent Runtime Vision V0.2 promotion bundle"
    )
    parser.add_argument("--bundle", required=True, help="JSON evidence bundle")
    parser.add_argument("--output", help="Optional JSON gate report")
    args = parser.parse_args()

    bundle = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    result = evaluate_promotion_bundle(bundle)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    raise SystemExit(0 if result["passed"] else 2)


if __name__ == "__main__":
    main()
