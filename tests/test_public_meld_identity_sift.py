from __future__ import annotations

import importlib.util
import json
import unittest

VISION = all(
    importlib.util.find_spec(name) is not None
    for name in ("cv2", "numpy", "PIL")
)


@unittest.skipUnless(VISION, "OpenCV/numpy/Pillow are optional in core-only installs")
class PublicMeldIdentitySiftTests(unittest.TestCase):
    def test_locked_queries_are_development_only_and_source_disjoint(self):
        from workspace.vision.evaluate_public_meld_sift_queries import (
            evaluate_public_meld_sift_queries,
        )

        report = evaluate_public_meld_sift_queries(".")
        self.assertEqual(report["query_count"], 2)
        self.assertFalse(report["changes_runtime_behavior"])
        self.assertFalse(report["formal_promotion_evidence"])
        self.assertFalse(report["safe_for_runtime"])
        self.assertFalse(report["safe_for_hint"])
        self.assertFalse(report["safe_for_executor"])
        for row in report["queries"]:
            self.assertTrue(row["source_disjoint_ranking"])
            self.assertGreaterEqual(row["minimum_other_match_groups"], 2)
            self.assertFalse(row["safe_for_runtime"])
            self.assertFalse(row["safe_for_executor"])

        print("PUBLIC_MELD_SIFT_EVAL=" + json.dumps(report, sort_keys=True))

    def test_blank_face_abstains(self):
        from PIL import Image
        from workspace.vision.public_identity_labels import (
            load_public_identity_manifest,
        )
        from workspace.vision.public_meld_identity_sift import (
            build_public_meld_sift_bank,
            rank_public_meld_sift,
        )

        bank = build_public_meld_sift_bank(
            load_public_identity_manifest(
                "references/vision/2026-09-22/public_identity_labels_v0_1.json"
            ),
            ".",
            "references/vision/2026-09-24/"
            "public_identity_source_groups.development.json",
        )
        result = rank_public_meld_sift(
            bank,
            Image.new("RGB", (80, 120), "white"),
            source_session="session_fba5f67d244fb5bd",
            source_sha256=(
                "fba5f67d244fb5bdc916f24707de288fef939a9444fa66bec21347e52bd64fc3"
            ),
        )
        self.assertIsNone(result["top1_tile"])
        self.assertEqual(result["reason"], "insufficient_sift_keypoints")
        self.assertFalse(result["safe_for_runtime"])


if __name__ == "__main__":
    unittest.main()
