import json
from pathlib import Path
import unittest


REPORT = Path(__file__).resolve().parents[1] / "references/vision/2026-10-03/sift_group_split_geometry_probe_v0_2.json"


class GroupSplitStageIsolationEvidenceTests(unittest.TestCase):
    def test_fixed_boundary_and_normalization_controls_do_not_recover_s9(self):
        report = json.loads(REPORT.read_text())
        self.assertEqual(report["schema_version"], "sift_group_split_geometry_probe_dev_v0_2")
        self.assertEqual(report["query_count"], 15)
        self.assertEqual(report["summary"]["direct_face_symmetric_geometry"]["legal_groups_correct"], 5)
        for mode in (
            "raw_group_equal_thirds_then_face_geometry",
            "group_normalize_equal_thirds_no_second_normalization",
            "group_normalize_split_then_face_geometry",
            "group_normalize_manual_roi_no_second_normalization",
            "group_normalize_manual_roi_boundary_counterfactual",
        ):
            self.assertEqual(report["summary"][mode]["correct_when_scorable"], 10)
            self.assertEqual(report["summary"][mode]["legal_groups_correct"], 0)
            self.assertTrue(all(row["modes"][mode]["top1"] != "S9"
                for row in report["rows"] if row["expected"] == "S9"))
        self.assertFalse(report["safe_for_runtime"])
        self.assertFalse(report["safe_for_hint"])
        self.assertFalse(report["safe_for_executor"])
