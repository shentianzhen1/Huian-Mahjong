import json
from pathlib import Path
import unittest


REPORT = Path(__file__).resolve().parents[1] / "references/vision/2026-10-03/hand8_boundary_band_pixels_v0_1.json"


class Hand8BoundaryBandEvidenceTests(unittest.TestCase):
    def test_s9_boundary_band_is_a_diagnostic_not_identity_promotion(self):
        report = json.loads(REPORT.read_text())
        s9 = [row for row in report["records"] if row["reviewed_candidate_tile"] == "S9"]
        self.assertEqual(len(s9), 5)
        self.assertTrue(all(row["omitted_raw_x_interval"] == [336, 338] for row in s9))
        self.assertEqual(report["s9_chromatic_body_pixels_in_omitted_bands"], 0)
        self.assertTrue(report["chromatic_test_does_not_prove_glyph_absence_or_sift_causality"])
        self.assertFalse(report["opencv_identity_rerank_performed"])
        self.assertFalse(report["safe_for_runtime"])
