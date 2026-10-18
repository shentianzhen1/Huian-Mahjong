import importlib.util
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


VISION = all(
    importlib.util.find_spec(name) is not None
    for name in ("PIL", "cv2", "numpy")
)


@unittest.skipUnless(VISION, "Pillow/OpenCV/numpy are optional in core-only installs")
class PublicMeldSiftFusionTests(unittest.TestCase):
    def test_cached_real_descriptors_follow_label_corrections_and_withdrawal(self):
        import numpy as np
        from workspace.vision import public_meld_sift_fusion as fusion
        from workspace.vision.tiles_v0_1.labels import approved_labels

        source = Path(__file__).resolve().parents[1] / "dataset/tiles_runtime_v0_2"
        row = next(row for row in approved_labels(source)
                   if row.get("region") == "hand_region" and row["tile_id"] == "S9"
                   and not row.get("gold_skin_only"))
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "dataset"
            root.mkdir()
            shutil.copyfile(source / row["image"], root / "face.png")
            label = {**row, "image": "face.png", "status": "approved", "approved": True}
            labels = root / "labels.jsonl"
            labels.write_text(json.dumps(label) + "\n", encoding="utf-8")
            cache_dir = Path(temporary) / "cache"
            with patch.object(fusion, "_build_hand_template_bank",
                              wraps=fusion._build_hand_template_bank) as build:
                cold = fusion.load_or_build_hand_template_bank(root, cache_dir=cache_dir)
                warm = fusion.load_or_build_hand_template_bank(root, cache_dir=cache_dir)
                self.assertEqual(len(cold), 1)
                self.assertEqual(build.call_count, 1)
                self.assertEqual(warm[0].tile_id, cold[0].tile_id)
                self.assertTrue(np.array_equal(warm[0].raw_descriptors, cold[0].raw_descriptors))
                self.assertEqual(len(warm[0].synthetic_descriptors), len(cold[0].synthetic_descriptors))
                for actual, expected in zip(warm[0].synthetic_descriptors, cold[0].synthetic_descriptors):
                    self.assertTrue(np.array_equal(actual, expected))
                label["tile_id"] = "S8"
                labels.write_text(json.dumps(label) + "\n", encoding="utf-8")
                corrected = fusion.load_or_build_hand_template_bank(root, cache_dir=cache_dir)
                self.assertEqual(corrected[0].tile_id, "S8")
                label.update(approved=False, status="rejected")
                labels.write_text(json.dumps(label) + "\n", encoding="utf-8")
                withdrawn = fusion.load_or_build_hand_template_bank(root, cache_dir=cache_dir)
                self.assertEqual(withdrawn, ())
                self.assertEqual(build.call_count, 3)

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
