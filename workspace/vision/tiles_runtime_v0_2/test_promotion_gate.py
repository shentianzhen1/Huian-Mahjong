from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from .promotion_gate import evaluate_promotion_bundle


def passing_bundle() -> dict:
    return {
        "provenance": {
            "independent_batch": True,
            "holdout_locked_before_evaluation": True,
            "tuning_after_lock": False,
            "source_sessions": 8,
        },
        "geometry": {
            "component_precision": 0.99,
            "component_recall": 0.99,
            "hand_count_exact_match_rate": 0.96,
            "runtime_region_errors": 0,
        },
        "tile_identity": {
            "standard_classes_covered": 34,
            "standard_classes_missing": 0,
            "accepted_accuracy": 0.995,
            "accepted_labels": 120,
        },
        "draw_temporal": {
            "events": 40,
            "precision": 0.99,
            "recall": 0.99,
            "duplicate_events": 0,
        },
        "public_state": {
            "score_points": 80,
            "score_pair_accuracy": 1.0,
            "status_points": 60,
            "remaining_tiles_accuracy": 1.0,
            "hand_index_accuracy": 0.99,
        },
        "gold": {
            "sessions": 8,
            "session_majority_accuracy": 1.0,
        },
        "stress": {
            "cases": 24,
            "unsafe_acceptances": 0,
        },
        "policy": {
            "safe_for_executor": False,
        },
    }


class PromotionGateTests(unittest.TestCase):
    def test_cli_writes_rejection_report_for_invalid_metrics(self) -> None:
        for bad in (float("inf"), float("nan"), "bad", {"nested": float("nan")}):
            with self.subTest(value=bad), tempfile.TemporaryDirectory() as directory:
                bundle = passing_bundle()
                bundle["tile_identity"]["accepted_accuracy"] = bad
                source = Path(directory) / "bundle.json"
                output = Path(directory) / "report.json"
                source.write_text(json.dumps(bundle), encoding="utf-8")
                process = subprocess.run(
                    [sys.executable, "-m", "workspace.vision.tiles_runtime_v0_2.promotion_gate",
                     "--bundle", str(source), "--output", str(output)],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(process.returncode, 2, process.stderr)
                report = json.loads(output.read_text(encoding="utf-8"))
                self.assertFalse(report["passed"])
                self.assertIn("tile_accepted_accuracy", report["failed_checks"])
                self.assertEqual(json.loads(process.stdout), report)
                json.dumps(report, allow_nan=False)

    def test_every_metric_rejects_invalid_domain_without_raising(self) -> None:
        valid = passing_bundle()
        for section, metrics in valid.items():
            for key, value in metrics.items():
                if type(value) is bool:
                    invalid = (0, 1, "true", [], {}, float("nan"))
                elif type(value) is int:
                    invalid = (True, False, -1, 1.5, "8", [], {},
                               float("nan"), float("inf"), float("-inf"))
                else:
                    invalid = (True, False, -0.01, 1.01, "0.99", [], {},
                               float("nan"), float("inf"), float("-inf"))
                for bad in invalid:
                    with self.subTest(metric=f"{section}.{key}", value=bad):
                        bundle = copy.deepcopy(valid)
                        bundle[section][key] = bad
                        result = evaluate_promotion_bundle(bundle)
                        self.assertFalse(result["passed"])
                        self.assertFalse(result["formal_runtime_baseline_ready"])
                        self.assertFalse(result["executor_ready"])
                        self.assertTrue(any(
                            check["reason"] in {
                                "invalid_boolean", "invalid_count_type", "negative_count",
                                "invalid_rate_type", "nonfinite_rate", "rate_out_of_range",
                            } for check in result["checks"]
                        ))
                        json.dumps(result, allow_nan=False)

    def test_integer_unit_rates_remain_valid(self) -> None:
        bundle = passing_bundle()
        for metrics in bundle.values():
            for key, value in metrics.items():
                if type(value) is float:
                    metrics[key] = 1
        self.assertTrue(evaluate_promotion_bundle(bundle)["passed"])

    def test_malformed_sections_and_root_fail_closed(self) -> None:
        for malformed in (None, [], "bad", 1):
            with self.subTest(root=malformed):
                self.assertFalse(evaluate_promotion_bundle(malformed)["passed"])
            for section in passing_bundle():
                with self.subTest(section=section, value=malformed):
                    bundle = passing_bundle()
                    bundle[section] = malformed
                    self.assertFalse(evaluate_promotion_bundle(bundle)["passed"])

    def test_complete_independent_bundle_can_promote_runtime_baseline_only(self) -> None:
        result = evaluate_promotion_bundle(passing_bundle())
        self.assertTrue(result["passed"])
        self.assertTrue(result["formal_runtime_baseline_ready"])
        self.assertFalse(result["executor_ready"])

    def test_missing_metric_fails_closed(self) -> None:
        bundle = passing_bundle()
        del bundle["draw_temporal"]["recall"]
        result = evaluate_promotion_bundle(bundle)
        self.assertFalse(result["passed"])
        self.assertIn("draw_event_recall", result["failed_checks"])

    def test_same_source_or_post_lock_tuning_cannot_promote(self) -> None:
        bundle = passing_bundle()
        bundle["provenance"]["independent_batch"] = False
        bundle["provenance"]["tuning_after_lock"] = True
        result = evaluate_promotion_bundle(bundle)
        self.assertFalse(result["passed"])
        self.assertIn("independent_batch", result["failed_checks"])
        self.assertIn("tuning_after_lock", result["failed_checks"])

    def test_single_silent_region_error_blocks_promotion(self) -> None:
        bundle = passing_bundle()
        bundle["geometry"]["runtime_region_errors"] = 1
        result = evaluate_promotion_bundle(bundle)
        self.assertFalse(result["passed"])
        self.assertIn("geometry_runtime_region_errors", result["failed_checks"])

    def test_good_accuracy_with_too_little_coverage_cannot_promote(self) -> None:
        bundle = passing_bundle()
        bundle["tile_identity"]["accepted_accuracy"] = 1.0
        bundle["tile_identity"]["accepted_labels"] = 50
        result = evaluate_promotion_bundle(bundle)
        self.assertFalse(result["passed"])
        self.assertIn("tile_accepted_labels", result["failed_checks"])

    def test_executor_true_is_rejected_even_if_every_metric_passes(self) -> None:
        bundle = passing_bundle()
        bundle["policy"]["safe_for_executor"] = True
        result = evaluate_promotion_bundle(bundle)
        self.assertFalse(result["passed"])
        self.assertIn("safe_for_executor_remains_false", result["failed_checks"])
        self.assertFalse(result["executor_ready"])


if __name__ == "__main__":
    unittest.main()
