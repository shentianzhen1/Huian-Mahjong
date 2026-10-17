from __future__ import annotations

import unittest

from workspace.vision.public_meld_identity_candidate import (
    FROZEN_CANDIDATE_ID,
    assert_holdout_is_eligible_for_frozen_candidate,
    load_public_meld_identity_candidate,
)


PATH = "references/vision/2026-10-01/public_meld_identity_candidate_v0_1.json"


class PublicMeldIdentityCandidateTests(unittest.TestCase):
    def test_repository_candidate_is_frozen_and_runtime_off(self):
        candidate = load_public_meld_identity_candidate(PATH)
        self.assertEqual(candidate.candidate_id, FROZEN_CANDIDATE_ID)
        self.assertEqual(candidate.inset_ratio, 0.12)
        self.assertEqual(
            candidate.selection_query_ids,
            ("first_hand_174s_p6", "first_hand_174s_s4"),
        )
        self.assertTrue(candidate.selected_on_selection_queries)
        self.assertEqual(candidate.normalization_scope, "query_side_split_face_only")
        self.assertFalse(candidate.template_bank_preprocessing_allowed)
        self.assertFalse(candidate.wire_into_runtime)
        self.assertFalse(candidate.safe_for_hint)
        self.assertFalse(candidate.safe_for_executor)
        self.assertFalse(candidate.formal_promotion_evidence)

    def test_independent_future_holdout_can_enter_scoring(self):
        candidate = load_public_meld_identity_candidate(PATH)
        assert_holdout_is_eligible_for_frozen_candidate(
            candidate,
            holdout_match_group="future_independent_match",
            candidate_changed_after_freeze=False,
            query_pixels_used_as_templates=False,
        )

    def test_selection_match_cannot_be_reused_as_holdout(self):
        candidate = load_public_meld_identity_candidate(PATH)
        with self.assertRaisesRegex(ValueError, "independent original match group"):
            assert_holdout_is_eligible_for_frozen_candidate(
                candidate,
                holdout_match_group=candidate.selection_match_group,
                candidate_changed_after_freeze=False,
                query_pixels_used_as_templates=False,
            )

    def test_candidate_change_or_template_leak_blocks_holdout(self):
        candidate = load_public_meld_identity_candidate(PATH)
        with self.assertRaisesRegex(ValueError, "changed after freeze"):
            assert_holdout_is_eligible_for_frozen_candidate(
                candidate,
                holdout_match_group="future_match",
                candidate_changed_after_freeze=True,
                query_pixels_used_as_templates=False,
            )
        with self.assertRaisesRegex(ValueError, "cannot be identity templates"):
            assert_holdout_is_eligible_for_frozen_candidate(
                candidate,
                holdout_match_group="future_match",
                candidate_changed_after_freeze=False,
                query_pixels_used_as_templates=True,
            )


if __name__ == "__main__":
    unittest.main()
