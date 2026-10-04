from __future__ import annotations

import json
from pathlib import Path
import unittest

from .evaluate_concealed_identity import (
    evaluate_concealed_identity,
    evaluate_regional_identity,
)


class ConcealedIdentityEvaluationTests(unittest.TestCase):
    def test_tracked_runtime_dataset_produces_diagnostic_holdout_report(self):
        root = Path(__file__).resolve().parents[3]
        report = evaluate_concealed_identity(
            root / "dataset" / "tiles_runtime_v0_2",
            confidence_threshold=0.82,
        )
        self.assertEqual(report["template_scope"], "concealed_identity")
        self.assertTrue(report["diagnostic_only"])
        self.assertFalse(report["changes_runtime_behavior"])
        self.assertFalse(report["safe_for_hint"])
        self.assertFalse(report["safe_for_executor"])
        self.assertGreater(report["distinct_source_groups"], 1)
        self.assertGreater(report["scorable_labels"], 0)
        regional = evaluate_regional_identity(
            root / "dataset" / "tiles_runtime_v0_2",
            confidence_threshold=0.82,
        )
        summary_keys = (
            "total_approved_labels",
            "scorable_labels",
            "unscorable_labels",
            "scorable_coverage",
            "exact_accuracy",
            "category_accuracy",
            "confidence_threshold",
            "accepted_labels",
            "accepted_fraction_of_scorable",
            "accepted_accuracy",
            "distinct_source_groups",
        )
        print(
            "CONCEALED_IDENTITY_EVAL="
            + json.dumps(
                {
                    **{key: report[key] for key in summary_keys},
                    "runtime_gate": report["runtime_gate"],
                },
                sort_keys=True,
            )
        )
        print(
            "REGIONAL_IDENTITY_EVAL="
            + json.dumps(
                {
                    **{key: regional[key] for key in summary_keys},
                    "runtime_gate": regional["runtime_gate"],
                },
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    unittest.main()
