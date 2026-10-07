from __future__ import annotations

import unittest

from workspace.vision.tiles_runtime_v0_2.template_source_consensus_probe import (
    summarize_scored_rows,
)


class TemplateSourceConsensusProbeTests(unittest.TestCase):
    def test_reports_max_exemplar_and_distinct_source_support_without_inference(self):
        rows = [
            {
                "tile_id": "M6",
                "score": 0.93,
                "sample_key": "m6-a",
                "source_session": "session_a",
                "source_sha256": "a" * 64,
                "source_frame": 10,
                "region": "hand_region",
                "image": "a.png",
            },
            {
                "tile_id": "M6",
                "score": 0.71,
                "sample_key": "m6-b",
                "source_session": "session_b",
                "source_sha256": "b" * 64,
                "source_frame": 20,
                "region": "draw_visual",
                "image": "b.png",
            },
            {
                "tile_id": "M7",
                "score": 0.89,
                "sample_key": "m7-a",
                "source_session": "session_c",
                "source_sha256": "c" * 64,
                "source_frame": 30,
                "region": "hand_region",
                "image": "c.png",
            },
        ]
        report = summarize_scored_rows(rows)
        self.assertEqual(report["top1_tile"], "M6")
        self.assertAlmostEqual(report["top1_score"], 0.93)
        self.assertEqual(report["top2_tile"], "M7")
        self.assertAlmostEqual(report["top1_top2_margin"], 0.04)
        m6 = report["class_ranking"][0]
        self.assertEqual(m6["distinct_source_session_count"], 2)
        self.assertAlmostEqual(m6["second_source_score"], 0.71)
        self.assertAlmostEqual(m6["top_two_source_mean"], 0.82)
        self.assertEqual(m6["winning_template"]["sample_key"], "m6-a")

    def test_single_source_class_keeps_consensus_diagnostics_unknown(self):
        report = summarize_scored_rows(
            [
                {
                    "tile_id": "M5",
                    "score": 0.84,
                    "sample_key": "only",
                    "source_session": "session_only",
                    "source_sha256": "d" * 64,
                    "source_frame": 1,
                    "region": "hand_region",
                    "image": "only.png",
                }
            ]
        )
        row = report["class_ranking"][0]
        self.assertEqual(row["distinct_source_session_count"], 1)
        self.assertIsNone(row["second_source_score"])
        self.assertIsNone(row["top_two_source_mean"])
        self.assertIsNone(report["top1_top2_margin"])

    def test_empty_input_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least one scored template"):
            summarize_scored_rows([])


if __name__ == "__main__":
    unittest.main()
