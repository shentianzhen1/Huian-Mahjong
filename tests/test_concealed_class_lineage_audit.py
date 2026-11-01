import unittest

from workspace.vision.concealed_class_lineage_audit import audit_class_lineage
from workspace.vision.concealed_template_match_lineage import ConcealedTemplateSource


class ConcealedClassLineageAuditTests(unittest.TestCase):
    def test_counts_reviewed_matches_not_sessions(self):
        sha_a = "a" * 64
        sha_b = "b" * 64
        sha_c = "c" * 64
        labels = [
            {
                "tile_id": "M6",
                "region": "hand_region",
                "approved": True,
                "sha256": sha_a,
                "source_session": "session-a",
            },
            {
                "tile_id": "M6",
                "region": "draw_region",
                "approved": True,
                "sha256": sha_b,
                "source_session": "session-b",
            },
            {
                "tile_id": "M6",
                "region": "draw_visual",
                "approved": True,
                "sha256": sha_c,
                "source_session": "session-c",
            },
        ]
        lineage = {
            sha_a: ConcealedTemplateSource(sha_a, "same-match", "evidence/a.json"),
            sha_b: ConcealedTemplateSource(sha_b, "same-match", "evidence/b.json"),
        }

        report = audit_class_lineage(labels, lineage)
        m6 = next(row for row in report["classes"] if row["tile_id"] == "M6")

        self.assertEqual(m6["ordinary_template_count"], 3)
        self.assertEqual(m6["distinct_source_session_count"], 3)
        self.assertEqual(m6["reviewed_original_match_group_count"], 1)
        self.assertEqual(m6["reviewed_original_match_groups"], ["same-match"])
        self.assertEqual(m6["unresolved_source_shas"], [sha_c])
        self.assertFalse(m6["source_session_used_as_independence_signal"])

    def test_excludes_gold_and_non_concealed_regions(self):
        sha = "d" * 64
        labels = [
            {
                "tile_id": "M6",
                "region": "hand_region",
                "approved": True,
                "sha256": sha,
                "source_session": "gold",
                "gold_skin_only": True,
            },
            {
                "tile_id": "M6",
                "region": "meld_region",
                "approved": True,
                "sha256": sha,
                "source_session": "meld",
            },
        ]

        report = audit_class_lineage(labels, {})
        m6 = next(row for row in report["classes"] if row["tile_id"] == "M6")
        self.assertEqual(m6["ordinary_template_count"], 0)
        self.assertIn("M6", report["classes_without_any_template"])


if __name__ == "__main__":
    unittest.main()
