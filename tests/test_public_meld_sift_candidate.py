from __future__ import annotations

import unittest

from workspace.vision.public_meld_sift_candidate import (
    CANDIDATE_ID,
    assert_future_sift_holdout_eligible,
    load_public_meld_sift_candidate,
)


PATH = "references/vision/2026-10-01/public_meld_sift_candidate_v0_1.json"


class PublicMeldSiftCandidateTests(unittest.TestCase):
    def test_repository_candidate_is_frozen_and_runtime_off(self):
        candidate = load_public_meld_sift_candidate(PATH)
        self.assertEqual(candidate.candidate_id, CANDIDATE_ID)
        self.assertEqual(candidate.scale_factor, 3.0)
        self.assertEqual(candidate.clahe_tile_grid, (8, 8))
        self.assertEqual(candidate.nfeatures, 100)
        self.assertEqual(candidate.ratio_test, 0.8)
        self.assertEqual(candidate.minimum_other_match_groups, 2)
        self.assertTrue(candidate.selected_after_reviewing_results)
        self.assertFalse(candidate.wire_into_runtime)
        self.assertFalse(candidate.safe_for_hint)
        self.assertFalse(candidate.safe_for_executor)
        self.assertFalse(candidate.formal_promotion_evidence)

    def test_only_new_match_group_can_be_future_holdout(self):
        candidate = load_public_meld_sift_candidate(PATH)
        known = {
            "reviewed_recording_66fe",
            "reviewed_recording_b389",
            "reviewed_match_2026_09_19_eight_hand",
            "reviewed_recording_14",
            "reviewed_match_2026_09_26_first_hand",
        }
        assert_future_sift_holdout_eligible(
            candidate,
            holdout_match_group="future_new_match",
            known_development_match_groups=known,
            candidate_changed_after_freeze=False,
            query_pixels_used_as_templates=False,
        )
        with self.assertRaisesRegex(ValueError, "new independent match group"):
            assert_future_sift_holdout_eligible(
                candidate,
                holdout_match_group="reviewed_recording_14",
                known_development_match_groups=known,
                candidate_changed_after_freeze=False,
                query_pixels_used_as_templates=False,
            )

    def test_candidate_change_or_template_leak_blocks_holdout(self):
        candidate = load_public_meld_sift_candidate(PATH)
        with self.assertRaisesRegex(ValueError, "changed after freeze"):
            assert_future_sift_holdout_eligible(
                candidate,
                holdout_match_group="future_new_match",
                known_development_match_groups=set(),
                candidate_changed_after_freeze=True,
                query_pixels_used_as_templates=False,
            )
        with self.assertRaisesRegex(ValueError, "cannot be templates"):
            assert_future_sift_holdout_eligible(
                candidate,
                holdout_match_group="future_new_match",
                known_development_match_groups=set(),
                candidate_changed_after_freeze=False,
                query_pixels_used_as_templates=True,
            )


if __name__ == "__main__":
    unittest.main()
