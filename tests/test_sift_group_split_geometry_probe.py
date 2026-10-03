import json
from pathlib import Path
import unittest


REPORT = Path(__file__).resolve().parents[1] / "references/vision/2026-10-03/sift_group_split_geometry_probe_v0_1.json"


class GroupSplitGeometryEvidenceTests(unittest.TestCase):
    def test_fixed_pipeline_regression_is_explicit_and_non_runtime(self):
        report = json.loads(REPORT.read_text())
        direct = report["summary"]["direct_face_symmetric_geometry"]
        grouped = report["summary"]["group_normalize_split_then_face_geometry"]
        self.assertEqual((direct["correct_when_scorable"], direct["legal_groups_correct"]), (15, 5))
        self.assertEqual((grouped["correct_when_scorable"], grouped["legal_groups_correct"]), (10, 0))
        self.assertEqual(report["candidate_decision"], "reject_group_pipeline_candidate_on_fixed_hand8_queries")
        self.assertFalse(report["runtime_integration"])
        self.assertFalse(report["safe_for_runtime"])

    def test_all_five_groups_only_assert_geometry_not_identity_truth(self):
        report = json.loads(REPORT.read_text())
        self.assertEqual(len(report["geometry"]), 5)
        self.assertTrue(all(row["stack_state"] == "FLAT" for row in report["geometry"]))
        self.assertTrue(all(row["input_faces_were_manual_rois_not_verified_splitter_outputs"] for row in report["geometry"]))
        self.assertFalse(report["manual_face_boundary_review"])
