from __future__ import annotations

import json
from pathlib import Path
import unittest

from workspace.vision.tiles_runtime_v0_2.shadow_glyph_ab import (
    build_shadow_glyph_ab_report,
)


ROOT = Path(__file__).resolve().parents[3]
DATASET = ROOT / "dataset" / "tiles_runtime_v0_2"


class ShadowGlyphABTests(unittest.TestCase):
    def test_tracked_reviewed_dataset_uses_identical_queries_and_raw_only_metrics(self):
        report = build_shadow_glyph_ab_report(DATASET)
        self.assertTrue(report["development_only"])
        self.assertFalse(report["runtime_changed"])
        self.assertFalse(report["source_session_is_independent_match_evidence"])
        self.assertFalse(report["candidate_score_calibrated_to_runtime_confidence"])
        self.assertFalse(report["runtime_threshold_metrics_valid_for_candidate"])
        for mode in report["modes"].values():
            self.assertGreater(mode["same_query_count"], 0)
            self.assertEqual(
                mode["baseline_raw"]["total"], mode["glyph_raw"]["total"]
            )
            self.assertEqual(mode["baseline_raw"]["total"], mode["same_query_count"])
            self.assertNotIn("accepted", mode["glyph_raw"])
        print("SHADOW_GLYPH_AB=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
