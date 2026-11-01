import json
from pathlib import Path
import unittest


REPORT = Path(__file__).resolve().parents[1] / "references/vision/2026-10-03/hand8_split_boundary_overlap_audit_v0_1.json"


class FixedBoundaryMappingTests(unittest.TestCase):
    def test_manual_roi_projection_is_stable_without_search_or_identity_claim(self):
        report = json.loads(REPORT.read_text())
        self.assertEqual(len(report["frames"]), 5)
        expected = [[0, 0, 75, 96], [72, 0, 74, 96], [141, 0, 75, 96]]
        for frame in report["frames"]:
            self.assertEqual([row["manual_roi_mapped_bbox"] for row in frame["faces"]], expected)
            self.assertEqual([row["omitted_normalized_x_pixels"] for row in frame["faces"]], [3, 2, 3])
        self.assertFalse(report["search_performed"])
        self.assertFalse(report["identity_rerank_performed"])
        self.assertFalse(report["manual_rois_are_exact_tile_polygons"])
        self.assertFalse(report["safe_for_runtime"])
