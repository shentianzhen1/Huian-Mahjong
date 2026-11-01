from __future__ import annotations

import json
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
PIN = REPO / "references/vision/2026-10-03/holdout3_p456_pre_score_pin_v0_1.json"
SPEC = REPO / "references/vision/2026-10-03/holdout3_p456_reference_complete_spec_v0_1.json"


class ReferenceCompleteHoldoutSpecTests(unittest.TestCase):
    def setUp(self):
        self.pin = json.loads(PIN.read_text(encoding="utf-8"))
        self.spec = json.loads(SPEC.read_text(encoding="utf-8"))

    def test_query_truth_was_pinned_before_scoring(self):
        source = self.spec["sources"][0]
        group = source["groups"][0]
        self.assertEqual(source["source_sha256"], self.pin["source"]["sha256"])
        self.assertEqual(
            group["frame_indices"],
            self.pin["query"]["stable_frames"],
        )
        self.assertEqual(
            group["reviewed_candidate_tiles"],
            self.pin["query"]["reviewed_left_to_right_tile_ids"],
        )
        self.assertTrue(
            self.pin["selection_policy"]["selected_before_identity_scoring"]
        )
        self.assertTrue(
            self.pin["selection_policy"]["no_score_based_video_selection"]
        )

    def test_weighted_formula_and_environment_are_frozen(self):
        contract = self.spec["scorer_contract"]
        self.assertEqual(
            contract["frozen_formula_commit"],
            "69893a5c0ca18ccb3128b70ce9695fa48512f047",
        )
        self.assertEqual(
            contract["score_policy"],
            "spatial_window_affine_reference_complete",
        )
        self.assertEqual(contract["reference_support_radius_normalized"], 0.08)
        self.assertEqual(contract["opencv_cv2"], "5.0.0")
        self.assertEqual(contract["numpy"], "2.5.3")
        self.assertFalse(contract["parameter_retuning_after_holdout"])

    def test_all_existing_crop_modes_are_predeclared(self):
        self.assertEqual(
            self.spec["scorer_contract"]["required_modes"],
            [
                "detector_seam2",
                "body_context_no_seam",
                "body_context_seam2",
                "outer_body_seam2",
                "face_plane_seam_boxes",
                "face_plane_seam_rectified",
                "face_plane_full_rectified",
            ],
        )
        self.assertEqual(
            self.spec["scorer_contract"]["crop_mode_policy"],
            "report_all_existing_detector_body_boundary_modes_no_posthoc_selection",
        )

    def test_same_original_match_is_not_misreported_as_independent_holdout(self):
        eligibility = self.spec["holdout_eligibility"]
        self.assertEqual(
            self.spec["conservative_original_match_group"],
            "drive_full_eight_one_original_match",
        )
        self.assertIn(
            "reviewed_match_2026_09_19_eight_hand",
            self.spec["excluded_same_match_aliases"],
        )
        self.assertFalse(eligibility["independent_original_match"])
        self.assertTrue(
            eligibility["same_original_match_as_existing_candidate_controls"]
        )
        self.assertEqual(
            eligibility["eligible_truth_classes_after_conservative_same_match_exclusion"],
            [],
        )
        self.assertEqual(
            eligibility["disposition"],
            "ABSTAIN_ALL_15_FACES_AS_UNKNOWN_FOR_FORMAL_HOLDOUT",
        )

    def test_holdout_remains_fail_closed(self):
        self.assertFalse(self.spec["formal_promotion_evidence"])
        self.assertFalse(self.spec["runtime_integration"])
        self.assertFalse(self.spec["safe_for_runtime"])
        self.assertFalse(self.spec["safe_for_hint"])
        self.assertFalse(self.spec["safe_for_executor"])


if __name__ == "__main__":
    unittest.main()
