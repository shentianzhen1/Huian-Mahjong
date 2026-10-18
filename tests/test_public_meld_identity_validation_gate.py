from __future__ import annotations

import unittest

from workspace.vision.public_meld_identity_validation_gate import (
    PublicMeldIdentityValidationEvidence,
    assess_public_meld_identity_validation,
    current_inset_candidate_evidence,
)


class PublicMeldIdentityValidationGateTests(unittest.TestCase):
    def test_current_12_percent_candidate_is_not_validation_evidence(self):
        result = assess_public_meld_identity_validation(
            current_inset_candidate_evidence()
        )
        self.assertFalse(result.eligible_as_validation_evidence)
        self.assertIn(
            "candidate_selected_on_evaluated_queries",
            result.blockers,
        )
        self.assertIn(
            "candidate_not_frozen_before_holdout",
            result.blockers,
        )
        self.assertIn(
            "holdout_not_source_disjoint",
            result.blockers,
        )
        report = result.to_dict()
        self.assertEqual(report["runtime_promotion_decision"], "NOT_DECIDED")
        self.assertFalse(report["changes_runtime_behavior"])
        self.assertFalse(report["safe_for_hint"])
        self.assertFalse(report["safe_for_executor"])

    def test_clean_future_holdout_can_be_called_validation_evidence_only(self):
        evidence = PublicMeldIdentityValidationEvidence(
            candidate_name="frozen_candidate",
            candidate_frozen_before_holdout=True,
            selected_on_evaluated_queries=False,
            source_disjoint_holdout=True,
            holdout_independent_match_groups=1,
            evaluated_class_count=2,
            identity_threshold_lowered=False,
            query_pixels_used_as_templates=False,
        )
        result = assess_public_meld_identity_validation(evidence)
        self.assertTrue(result.eligible_as_validation_evidence)
        self.assertEqual(result.blockers, ())
        self.assertEqual(
            result.to_dict()["runtime_promotion_decision"],
            "NOT_DECIDED",
        )

    def test_each_evidence_leak_or_policy_break_fails_closed(self):
        base = dict(
            candidate_name="candidate",
            candidate_frozen_before_holdout=True,
            selected_on_evaluated_queries=False,
            source_disjoint_holdout=True,
            holdout_independent_match_groups=1,
            evaluated_class_count=2,
            identity_threshold_lowered=False,
            query_pixels_used_as_templates=False,
        )
        cases = [
            ("candidate_frozen_before_holdout", False, "candidate_not_frozen_before_holdout"),
            ("selected_on_evaluated_queries", True, "candidate_selected_on_evaluated_queries"),
            ("source_disjoint_holdout", False, "holdout_not_source_disjoint"),
            ("holdout_independent_match_groups", 0, "no_independent_holdout_match_group"),
            ("evaluated_class_count", 0, "no_evaluated_holdout_class"),
            ("identity_threshold_lowered", True, "identity_threshold_lowered"),
            ("query_pixels_used_as_templates", True, "query_pixels_used_as_templates"),
        ]
        for field, value, blocker in cases:
            with self.subTest(field=field):
                payload = dict(base)
                payload[field] = value
                result = assess_public_meld_identity_validation(
                    PublicMeldIdentityValidationEvidence(**payload)
                )
                self.assertFalse(result.eligible_as_validation_evidence)
                self.assertIn(blocker, result.blockers)

    def test_invalid_counts_are_rejected(self):
        with self.assertRaises(ValueError):
            PublicMeldIdentityValidationEvidence(
                candidate_name="bad",
                candidate_frozen_before_holdout=True,
                selected_on_evaluated_queries=False,
                source_disjoint_holdout=True,
                holdout_independent_match_groups=-1,
                evaluated_class_count=1,
                identity_threshold_lowered=False,
                query_pixels_used_as_templates=False,
            )


if __name__ == "__main__":
    unittest.main()
