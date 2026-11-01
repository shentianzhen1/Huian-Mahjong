import unittest

from workspace.vision.tiles_runtime_v0_2.opened_gold_direct_holdout_readiness import (
    ELIGIBLE_FOR_LEAVE_ONE_MATCH_OUT,
    NO_REVIEWED_DIRECT_REFERENCE,
    ONE_REVIEWED_ORIGINAL_MATCH_NO_HOLDOUT,
    audit_direct_gold_holdout_readiness,
    validate_evidence_entries,
)


class OpenedGoldDirectHoldoutReadinessTests(unittest.TestCase):
    @staticmethod
    def _row(tile, group, source, *, checkpoints=1, status="REVIEWED"):
        return {
            "tile_id": tile,
            "evidence_kind": "reviewed_detector_gold_indicator",
            "source_sha256": source,
            "original_match_group": group,
            "lineage_status": status,
            "evidence_path": "references/evidence.json",
            "checkpoint_count": checkpoints,
        }

    def test_repeated_checkpoints_in_one_match_are_one_independence_unit(self):
        rows = [self._row("M6", "match_a", "a" * 64, checkpoints=40)]
        report = audit_direct_gold_holdout_readiness(rows)
        detail = report["per_class"]["M6"]
        self.assertEqual(detail["checkpoint_count"], 40)
        self.assertEqual(detail["reviewed_original_match_count"], 1)
        self.assertEqual(detail["readiness"], ONE_REVIEWED_ORIGINAL_MATCH_NO_HOLDOUT)
        self.assertFalse(detail["checkpoint_count_is_independence_count"])
        self.assertFalse(report["adjacent_frames_are_independent_sources"])

    def test_same_match_different_records_still_do_not_create_holdout(self):
        rows = [
            self._row("P9", "match_a", "a" * 64),
            self._row("P9", "match_a", "b" * 64),
        ]
        report = audit_direct_gold_holdout_readiness(rows)
        detail = report["per_class"]["P9"]
        self.assertEqual(detail["evidence_record_count"], 2)
        self.assertEqual(detail["reviewed_original_match_count"], 1)
        self.assertEqual(detail["readiness"], ONE_REVIEWED_ORIGINAL_MATCH_NO_HOLDOUT)
        self.assertFalse(report["same_match_different_clips_are_independent_sources"])

    def test_two_reviewed_original_matches_enable_leave_one_match_out(self):
        rows = [
            self._row("N", "match_a", "a" * 64),
            self._row("N", "match_b", "b" * 64),
        ]
        report = audit_direct_gold_holdout_readiness(rows)
        detail = report["per_class"]["N"]
        self.assertEqual(detail["reviewed_original_match_count"], 2)
        self.assertEqual(detail["readiness"], ELIGIBLE_FOR_LEAVE_ONE_MATCH_OUT)
        self.assertEqual(report["eligible_for_leave_one_match_out_classes"], ["N"])

    def test_unknown_lineage_is_not_reviewed_support(self):
        rows = [self._row("S3", None, "c" * 64, status="UNKNOWN")]
        report = audit_direct_gold_holdout_readiness(rows)
        detail = report["per_class"]["S3"]
        self.assertEqual(detail["reviewed_original_match_count"], 0)
        self.assertEqual(detail["readiness"], NO_REVIEWED_DIRECT_REFERENCE)
        self.assertEqual(detail["unknown_lineage_evidence_record_count"], 1)

    def test_reviewed_entry_without_original_match_fails_closed(self):
        row = self._row("M1", None, "d" * 64)
        with self.assertRaisesRegex(ValueError, "requires original_match_group"):
            validate_evidence_entries([row])

    def test_report_never_claims_accuracy_or_changes_runtime(self):
        report = audit_direct_gold_holdout_readiness(
            [self._row("M6", "match_a", "a" * 64)]
        )
        self.assertFalse(report["accuracy_claimed"])
        self.assertFalse(report["runtime_changed"])
        self.assertFalse(report["runtime_identity_threshold_changed"])
        self.assertEqual(report["runtime_identity_threshold_reference"], 0.82)
        self.assertFalse(report["formal_promotion_evidence"])


if __name__ == "__main__":
    unittest.main()
