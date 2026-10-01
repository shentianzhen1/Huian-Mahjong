from __future__ import annotations

import importlib.util
import json
import unittest

VISION = all(importlib.util.find_spec(name) is not None for name in ("cv2","numpy","PIL"))


@unittest.skipUnless(VISION, "OpenCV/numpy/Pillow are optional in core-only installs")
class Hand1P6PublicMeldSiftQueryTests(unittest.TestCase):
    def test_real_p6_query_is_source_disjoint_development_only(self):
        from workspace.vision.evaluate_public_meld_sift_queries import (
            evaluate_public_meld_sift_queries,
        )

        report = evaluate_public_meld_sift_queries(
            ".",
            "references/vision/2026-10-01/hand1_p6_kong_public_query_v0_1.json",
            minimum_other_match_groups=2,
        )
        self.assertEqual(report["query_count"], 1)
        row = report["queries"][0]
        self.assertEqual(row["query_id"], "hand1_p6_kong_frame360_public_meld_face")
        self.assertEqual(row["expected_tile"], "P6")
        self.assertTrue(row["source_disjoint_ranking"])
        self.assertEqual(row["minimum_other_match_groups"], 2)
        self.assertFalse(row["formal_promotion_evidence"])
        self.assertFalse(row["safe_for_runtime"])
        self.assertFalse(row["safe_for_hint"])
        self.assertFalse(row["safe_for_executor"])
        self.assertFalse(report["changes_runtime_behavior"])
        self.assertFalse(report["formal_promotion_evidence"])
        print("ISSUE69_HAND1_P6_PUBLIC_MELD_SIFT=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
