import unittest

from workspace.vision.concealed_template_match_lineage import ConcealedTemplateSource
from workspace.vision.tiles_runtime_v0_2.opened_gold_reference_coverage import (
    audit_opened_gold_reference_coverage,
)


class OpenedGoldReferenceCoverageTests(unittest.TestCase):
    @staticmethod
    def _source(sha, group):
        return ConcealedTemplateSource(sha, group, "evidence.json")

    @staticmethod
    def _row(tile, sha, session, *, region="hand_region", gold_skin_only=False):
        return {
            "tile_id": tile,
            "sha256": sha,
            "source_session": session,
            "source_id": f"src_{session}",
            "region": region,
            "approved": True,
            "gold_skin_only": gold_skin_only,
            "image": f"templates/{tile}_{session}.png",
        }

    def test_same_match_different_sessions_do_not_count_as_reviewed_cross_match(self):
        sha_a = "a" * 64
        sha_b = "b" * 64
        labels = [
            self._row("M1", sha_a, "session_a"),
            self._row("M1", sha_b, "session_b"),
        ]
        lineage = {
            sha_a: self._source(sha_a, "match_one"),
            sha_b: self._source(sha_b, "match_one"),
        }
        report = audit_opened_gold_reference_coverage(labels, lineage)
        comparison = report["independence_comparison"]
        self.assertEqual(comparison["legacy_cross_session_classes"], ["M1"])
        self.assertEqual(comparison["reviewed_cross_match_classes"], [])
        self.assertEqual(
            comparison["legacy_cross_session_but_not_reviewed_cross_match_classes"],
            ["M1"],
        )
        self.assertFalse(report["source_session_is_independence_signal"])

    def test_two_reviewed_matches_count_as_reviewed_cross_match(self):
        sha_a = "a" * 64
        sha_b = "b" * 64
        labels = [
            self._row("P9", sha_a, "session_a"),
            self._row("P9", sha_b, "session_b"),
        ]
        lineage = {
            sha_a: self._source(sha_a, "match_one"),
            sha_b: self._source(sha_b, "match_two"),
        }
        report = audit_opened_gold_reference_coverage(labels, lineage)
        comparison = report["independence_comparison"]
        self.assertEqual(comparison["reviewed_cross_match_classes"], ["P9"])
        self.assertEqual(
            comparison["legacy_cross_session_but_not_reviewed_cross_match_classes"],
            [],
        )

    def test_unknown_lineage_cannot_create_reviewed_independence(self):
        sha_a = "a" * 64
        sha_unknown = "c" * 64
        labels = [
            self._row("S7", sha_a, "session_a"),
            self._row("S7", sha_unknown, "session_unknown"),
        ]
        lineage = {sha_a: self._source(sha_a, "match_one")}
        report = audit_opened_gold_reference_coverage(labels, lineage)
        detail = report["independence_comparison"]["legacy_only_details"][0]
        self.assertEqual(detail["tile_id"], "S7")
        self.assertEqual(detail["unknown_lineage_label_count"], 1)
        self.assertEqual(detail["reviewed_original_match_group_count"], 1)

    def test_direct_gold_and_gold_skin_evidence_are_reported_separately(self):
        sha_gold = "a" * 64
        sha_skin = "b" * 64
        labels = [
            self._row("N", sha_gold, "session_gold", region="gold_region"),
            self._row(
                "M6",
                sha_skin,
                "session_skin",
                region="hand_region",
                gold_skin_only=True,
            ),
        ]
        lineage = {
            sha_gold: self._source(sha_gold, "match_gold"),
            sha_skin: self._source(sha_skin, "match_skin"),
        }
        report = audit_opened_gold_reference_coverage(labels, lineage)
        self.assertEqual(report["direct_gold_region_references"]["classes"], ["N"])
        self.assertEqual(report["real_gold_skin_evidence"]["classes"], ["M6"])
        self.assertFalse(report["runtime_changed"])
        self.assertFalse(report["runtime_identity_threshold_changed"])

    def test_unapproved_labels_are_ignored(self):
        sha_a = "a" * 64
        row = self._row("P1", sha_a, "session_a")
        row["approved"] = False
        report = audit_opened_gold_reference_coverage([row], {})
        self.assertEqual(report["approved_label_count"], 0)
        self.assertEqual(
            report["independence_comparison"]["legacy_cross_session_classes"],
            [],
        )


if __name__ == "__main__":
    unittest.main()
