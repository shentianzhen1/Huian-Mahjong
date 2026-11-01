import json
from pathlib import Path
import unittest

from workspace.vision.tiles_runtime_v0_2.whole_hand_eval import (
    FROZEN_CONFIDENCE_THRESHOLD,
)


SEED = Path(
    "references/vision/2026-10-07/"
    "whole_hand_truth_seed_20260926_first_hand_v0_1.json"
)
SOURCE_SHA = "fba5f67d244fb5bdc916f24707de288fef939a9444fa66bec21347e52bd64fc3"


class WholeHandTruthSeed20260926Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(SEED.read_text(encoding="utf-8"))
        cls.by_time = {
            float(sample["timestamp_seconds"]): sample
            for sample in cls.payload["samples"]
        }

    def test_source_and_frozen_threshold_are_pinned(self):
        self.assertEqual(self.payload["source"]["sha256"], SOURCE_SHA)
        self.assertEqual(self.payload["source_grouping"]["original_match_group"], "reviewed_match_2026_09_26_first_hand")
        self.assertEqual(self.payload["review"]["confidence_threshold"], 0.82)
        self.assertEqual(FROZEN_CONFIDENCE_THRESHOLD, 0.82)
        self.assertTrue(self.payload["evaluation_policy"]["exact_source_filtered_baseline_required"])
        self.assertFalse(self.payload["evaluation_policy"]["formal_original_match_disjoint_promotion_evidence"])

    def test_expected_checkpoints_are_exactly_pinned(self):
        self.assertEqual(sorted(self.by_time), [40.0, 52.0, 110.0, 175.0])

    def test_40s_triplet_moves_into_52s_daiminkan(self):
        hand40 = self.by_time[40.0]["truth"]["concealed_hand"]
        truth52 = self.by_time[52.0]["truth"]
        self.assertEqual(hand40.count("P6"), 3)
        self.assertEqual(truth52["own_melds"], [["P6", "P6", "P6", "P6"]])
        self.assertNotIn("P6", truth52["concealed_hand"])

    def test_110s_second_meld_and_draw_are_locked(self):
        truth = self.by_time[110.0]["truth"]
        self.assertEqual(truth["own_melds"][1], ["S3", "S4", "S5"])
        self.assertEqual(truth["draw_visual"], "S2")
        self.assertEqual(truth["gold_skinned_concealed_slots"], [0, 1])
        self.assertEqual(truth["concealed_hand"][:2], ["M6", "M6"])

    def test_175s_terminal_checkpoint_keeps_youjin_draw_truth(self):
        sample = self.by_time[175.0]
        truth = sample["truth"]
        self.assertIn("youjin_prompt_overlay", sample["scene_tags"])
        self.assertEqual(truth["draw_visual"], "P4")
        self.assertEqual(truth["own_melds"], [
            ["P6", "P6", "P6", "P6"],
            ["S3", "S4", "S5"],
        ])
        self.assertEqual(len(truth["concealed_hand"]), 10)


if __name__ == "__main__":
    unittest.main()
