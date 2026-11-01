import unittest

from workspace.vision.concealed_template_match_lineage import ConcealedTemplateSource
from workspace.vision.tiles_runtime_v0_2.template_source_consensus_probe import (
    annotate_scored_rows_with_lineage,
    summarize_scored_rows,
)


class TemplateSourceConsensusLineageTests(unittest.TestCase):
    def test_two_sessions_from_same_match_count_once(self):
        sha_a = "a" * 64
        sha_b = "b" * 64
        sha_c = "c" * 64
        lineage = {
            sha_a: ConcealedTemplateSource(sha_a, "match-one", "evidence/a.json"),
            sha_b: ConcealedTemplateSource(sha_b, "match-one", "evidence/b.json"),
            sha_c: ConcealedTemplateSource(sha_c, "match-two", "evidence/c.json"),
        }
        rows = [
            {
                "tile_id": "M6",
                "score": 0.99,
                "sample_key": "a",
                "source_session": "session-a",
                "source_sha256": sha_a,
            },
            {
                "tile_id": "M6",
                "score": 0.97,
                "sample_key": "b",
                "source_session": "session-b",
                "source_sha256": sha_b,
            },
            {
                "tile_id": "M6",
                "score": 0.91,
                "sample_key": "c",
                "source_session": "session-c",
                "source_sha256": sha_c,
            },
        ]

        summary = summarize_scored_rows(
            annotate_scored_rows_with_lineage(rows, lineage)
        )
        m6 = summary["class_ranking"][0]

        self.assertEqual(m6["distinct_source_session_count"], 3)
        self.assertEqual(m6["reviewed_original_match_group_count"], 2)
        self.assertEqual(
            [row["original_match_group"] for row in m6["per_original_match_group_max"]],
            ["match-one", "match-two"],
        )
        self.assertAlmostEqual(m6["second_original_match_score"], 0.91)
        self.assertFalse(m6["source_session_used_as_independence_signal"])

    def test_unknown_sha_never_adds_independent_match_support(self):
        known_sha = "d" * 64
        unknown_sha = "e" * 64
        lineage = {
            known_sha: ConcealedTemplateSource(
                known_sha, "reviewed-match", "evidence/known.json"
            )
        }
        rows = [
            {
                "tile_id": "M6",
                "score": 1.0,
                "sample_key": "unknown-winner",
                "source_session": "unique-looking-session",
                "source_sha256": unknown_sha,
            },
            {
                "tile_id": "M6",
                "score": 0.90,
                "sample_key": "known",
                "source_session": "known-session",
                "source_sha256": known_sha,
            },
        ]

        summary = summarize_scored_rows(
            annotate_scored_rows_with_lineage(rows, lineage)
        )
        m6 = summary["class_ranking"][0]

        self.assertEqual(m6["winning_template"]["original_match_group"], None)
        self.assertFalse(m6["winning_template"]["lineage_qualified"])
        self.assertEqual(m6["reviewed_original_match_group_count"], 1)
        self.assertEqual(m6["unresolved_source_sha_count"], 1)
        self.assertEqual(m6["unresolved_source_shas"], [unknown_sha])
        self.assertEqual(summary["top1_reviewed_original_match_group_count"], 1)
        self.assertEqual(summary["top1_unresolved_source_sha_count"], 1)

    def test_match_aggregation_is_per_tile_class(self):
        sha_a = "1" * 64
        sha_b = "2" * 64
        lineage = {
            sha_a: ConcealedTemplateSource(sha_a, "match-a", "evidence/a.json"),
            sha_b: ConcealedTemplateSource(sha_b, "match-b", "evidence/b.json"),
        }
        rows = [
            {
                "tile_id": "M6",
                "score": 0.94,
                "sample_key": "m6",
                "source_session": "same-session-name",
                "source_sha256": sha_a,
            },
            {
                "tile_id": "M7",
                "score": 0.93,
                "sample_key": "m7",
                "source_session": "same-session-name",
                "source_sha256": sha_b,
            },
        ]

        summary = summarize_scored_rows(
            annotate_scored_rows_with_lineage(rows, lineage)
        )

        self.assertEqual(summary["top1_tile"], "M6")
        self.assertEqual(summary["top2_tile"], "M7")
        self.assertEqual(
            summary["class_ranking"][0]["reviewed_original_match_group_count"], 1
        )
        self.assertEqual(
            summary["class_ranking"][1]["reviewed_original_match_group_count"], 1
        )


if __name__ == "__main__":
    unittest.main()
