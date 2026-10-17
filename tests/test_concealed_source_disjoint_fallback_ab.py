import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "references/vision/2026-10-08/concealed_source_disjoint_fallback_ab_v0_1.json"
STAGING = ROOT / "references/vision/2026-10-08/reviewed_tile_intake_staging_20260926_support_expansion.jsonl"
M2_STAGING = ROOT / "references/vision/2026-10-08/reviewed_tile_intake_staging_20260926_m2.jsonl"


class ConcealedSourceDisjointFallbackABTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))
        cls.rows = [json.loads(line) for line in STAGING.read_text(encoding="utf-8").splitlines() if line.strip()]
        cls.m2_rows = [json.loads(line) for line in M2_STAGING.read_text(encoding="utf-8").splitlines() if line.strip()]

    def test_support_assets_stay_one_original_match(self):
        support = self.report["support"]
        self.assertTrue(support["all_support_assets_count_as_one_original_match"])
        self.assertEqual(support["original_match_group"], "reviewed_match_2026_09_26_eight_hand")
        self.assertEqual({row["sha256"] for row in self.rows + self.m2_rows}, {support["source_sha256"]})
        self.assertEqual({row["source_session"] for row in self.rows + self.m2_rows}, {support["source_session"]})

    def test_support_and_query_are_different_original_matches_but_query_is_not_fresh_holdout(self):
        report = self.report
        self.assertNotEqual(report["support"]["original_match_group"], report["query"]["original_match_group"])
        self.assertTrue(report["query"]["revealed_development_match"])
        self.assertFalse(report["query"]["fresh_promotion_holdout"])
        self.assertFalse(report["formal_promotion_evidence"])

    def test_staging_assets_are_reviewed_but_not_wired(self):
        self.assertEqual(len(self.rows), 8)
        self.assertEqual({row["tile_id"] for row in self.rows}, {"M1", "P2", "S3", "S4", "S7"})
        self.assertTrue(all(row["approved"] for row in self.rows))
        self.assertTrue(all(row["asset_role"] == "development_prototype_only" for row in self.rows))
        support = self.report["support"]
        self.assertFalse(support["binary_assets_committed"])
        self.assertFalse(support["final_labels_updated"])
        self.assertFalse(support["runtime_template_bank_updated"])

    def test_primary_support_expansion_improves_coverage_without_wrong_accepts(self):
        baseline = self.report["baseline_runtime"]
        primary = self.report["support_expansion_primary_crop_only"]
        self.assertEqual((baseline["runtime_accepted_correct"], baseline["runtime_wrong_accepted"], baseline["runtime_rejected"]), (25, 0, 18))
        self.assertEqual((primary["runtime_accepted_correct"], primary["runtime_wrong_accepted"], primary["runtime_rejected"]), (35, 0, 8))
        self.assertGreater(primary["raw_top1_correct"], baseline["raw_top1_correct"])

    def test_primary_first_fallback_closes_revealed_43_without_threshold_change(self):
        fallback = self.report["conservative_tight_fallback"]
        self.assertEqual(fallback["runtime_identity_threshold"], 0.82)
        self.assertFalse(fallback["threshold_changed"])
        self.assertEqual((fallback["accepted_correct"], fallback["wrong_accepted"], fallback["rejected"]), (43, 0, 0))
        self.assertEqual((fallback["whole_hands_complete"], fallback["whole_hands_total"]), (3, 3))
        self.assertTrue(all(row["complete"] for row in fallback["per_hand"]))

    def test_fallback_never_overrides_primary_and_global_tight_replacement_is_rejected(self):
        fallback = self.report["conservative_tight_fallback"]
        self.assertIn("Never override an identity already accepted by the primary Runtime path.", fallback["policy"])
        self.assertTrue(fallback["important_negative_control"]["tight_crop_as_global_replacement_rejected"])

    def test_runtime_agent_and_executor_boundaries_remain_frozen(self):
        report = self.report
        self.assertFalse(report["runtime_changed"])
        self.assertEqual(report["runtime_identity_threshold"], 0.82)
        self.assertEqual(report["current_agent"], "MeldAwareShantenAgent V0.10")
        self.assertEqual(report["hint_alpha"], "internal_read_only")
        self.assertFalse(report["executor_enabled"])
        self.assertFalse(report["safe_for_runtime"])
        self.assertFalse(report["safe_for_hint_promotion"])
        self.assertFalse(report["safe_for_executor"])


if __name__ == "__main__":
    unittest.main()
