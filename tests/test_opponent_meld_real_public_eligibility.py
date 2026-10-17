from pathlib import Path
import unittest

from workspace.vision.opponent_meld_real_public_eligibility import run

ROOT = Path(__file__).resolve().parents[1]


class OpponentMeldRealPublicEligibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run(ROOT)

    def test_s456_has_cross_match_real_public_references(self):
        row = self.report["queries"]["s456"]
        self.assertTrue(row["real_public_probe_eligible"])
        self.assertEqual(row["status"], "ELIGIBLE_DEVELOPMENT_ONLY")
        for tile in ("S4", "S5", "S6"):
            coverage = row["cross_match_real_reference_coverage"][tile]
            self.assertGreaterEqual(coverage["cross_match_real_face_count"], 1)
            self.assertNotIn(
                row["query_match_group"],
                coverage["labels_by_match_group"],
            )

    def test_m123_is_blocked_without_cross_match_real_public_references(self):
        row = self.report["queries"]["m123"]
        self.assertFalse(row["real_public_probe_eligible"])
        self.assertEqual(
            row["status"],
            "BLOCKED_MISSING_CROSS_MATCH_REAL_PUBLIC_REFERENCE",
        )
        for tile in ("M1", "M2", "M3"):
            coverage = row["cross_match_real_reference_coverage"][tile]
            self.assertEqual(coverage["cross_match_real_face_count"], 0)
            self.assertEqual(coverage["independent_match_group_count"], 0)

    def test_s123_is_blocked_only_by_missing_s1_real_public_reference(self):
        row = self.report["queries"]["s123"]
        self.assertFalse(row["real_public_probe_eligible"])
        self.assertEqual(
            row["status"],
            "BLOCKED_MISSING_CROSS_MATCH_REAL_PUBLIC_REFERENCE",
        )
        coverage = row["cross_match_real_reference_coverage"]
        self.assertEqual(coverage["S1"]["cross_match_real_face_count"], 0)
        self.assertGreaterEqual(coverage["S2"]["cross_match_real_face_count"], 1)
        self.assertGreaterEqual(coverage["S3"]["cross_match_real_face_count"], 1)

    def test_gate_is_development_only(self):
        self.assertTrue(self.report["same_match_reference_forbidden"])
        self.assertFalse(self.report["changes_runtime_behavior"])
        self.assertFalse(self.report["formal_promotion_evidence"])
        self.assertFalse(self.report["safe_for_runtime"])
        self.assertFalse(self.report["safe_for_hint"])
        self.assertFalse(self.report["safe_for_executor"])


if __name__ == "__main__":
    unittest.main()
