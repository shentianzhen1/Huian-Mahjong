import importlib.util
import unittest


VISION = all(
    importlib.util.find_spec(name) is not None
    for name in ("PIL", "cv2", "numpy")
)


@unittest.skipUnless(VISION, "Pillow/OpenCV/numpy are optional in core-only installs")
class PublicMeldSiftFusionTests(unittest.TestCase):
    def test_rank_percentile_fusion_is_scale_independent(self):
        from workspace.vision.public_meld_sift_fusion import (
            fuse_rank_percentile_scores,
        )

        real = {"P6": 0.01, "P7": 0.008, "P8": 0.004}
        synthetic = {"P6": 500.0, "P7": 300.0, "P8": 10.0}
        fused = fuse_rank_percentile_scores(real, synthetic)

        self.assertGreater(fused["P6"], fused["P7"])
        self.assertGreater(fused["P7"], fused["P8"])
        self.assertEqual(fused["P6"], 1.0)

    def test_missing_class_coverage_is_not_negative_evidence(self):
        from workspace.vision.public_meld_sift_fusion import (
            fuse_rank_percentile_scores,
        )

        fused = fuse_rank_percentile_scores(
            {"P6": 3.0, "P7": 2.0},
            {"P8": 9.0, "P9": 1.0},
        )

        self.assertEqual(fused["P6"], 1.0)
        self.assertEqual(fused["P8"], 1.0)
        self.assertIn("P7", fused)
        self.assertIn("P9", fused)

    def test_repository_small_batch_runs_fail_closed(self):
        from workspace.vision.public_meld_sift_fusion import (
            evaluate_public_meld_sift_fusion,
        )

        report = evaluate_public_meld_sift_fusion()

        self.assertEqual(report["schema_version"], "public_meld_sift_fusion_v0_1")
        self.assertEqual(report["target_group_count"], 7)
        self.assertEqual(report["scored_group_count"], 7)
        self.assertEqual(report["scored_face_count"], 21)
        self.assertTrue(report["real_branch_exact_target_group_excluded"])
        self.assertFalse(report["real_branch_source_disjoint_by_original_match"])
        self.assertFalse(report["blind_validation"])
        self.assertFalse(report["opponent_top_group_accuracy_measured"])
        self.assertFalse(report["changes_runtime_behavior"])
        self.assertFalse(report["formal_promotion_evidence"])
        self.assertFalse(report["safe_for_runtime"])
        self.assertFalse(report["safe_for_hint"])
        self.assertFalse(report["safe_for_executor"])


if __name__ == "__main__":
    unittest.main()
