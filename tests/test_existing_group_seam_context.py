import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SeamContextDevelopmentEvidenceTests(unittest.TestCase):
    def test_restored_hand8_ranking_and_scorable_control_remain_development_only(self):
        hand8 = json.loads((ROOT / "references/vision/2026-10-03/sift_group_split_geometry_probe_v0_3.json").read_text())
        controls = json.loads((ROOT / "references/vision/2026-10-03/existing_group_seam_context_v0_1.json").read_text())
        candidate = hand8["summary"]["raw_equal_thirds_two_pixel_seam_context_then_face_geometry"]
        self.assertEqual((candidate["correct_when_scorable"], candidate["legal_groups_correct"]), (15, 5))
        self.assertEqual(hand8["summary"]["raw_group_equal_thirds_then_face_geometry"]["legal_groups_correct"], 0)
        s8 = controls["summary"]["raw_equal_thirds_two_pixel_seam_context"]["hand7_bamboo8"]
        self.assertEqual((s8["scorable"], s8["correct_when_scorable"], s8["group_frame_correct_when_scorable"]), (15, 15, 5))
        for group in ("hand3_north", "hand3_bamboo1", "hand8_wan9"):
            self.assertEqual(controls["summary"]["raw_equal_thirds_two_pixel_seam_context"][group]["scorable"], 0)
        self.assertTrue(controls["two_pixel_margin_chosen_after_hand8_inspection"])
        self.assertFalse(controls["independent_holdout"])
        self.assertFalse(hand8["safe_for_runtime"])
        self.assertFalse(controls["safe_for_runtime"])
