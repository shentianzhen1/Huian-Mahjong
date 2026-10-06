import unittest

from workspace.vision.public_meld_stacked_identity_decoder import (
    VISIBLE_ROLES,
    rank_stacked_visible_identity,
)


class StackedVisibleIdentityTests(unittest.TestCase):
    def rank(self, rows, **kwargs):
        return rank_stacked_visible_identity(
            rows, source_frame_verified=kwargs.get("source_frame_verified", True),
            visible_faces_reviewed=kwargs.get("visible_faces_reviewed", True),
        )

    def test_agreement_never_fabricates_fourth_tile_or_runtime_acceptance(self):
        result = self.rank({role: {"P6": .9, "P8": .2} for role in VISIBLE_ROLES})
        self.assertEqual(result["top_tile"], "P6")
        self.assertTrue(result["visible_top1_agreement"])
        self.assertEqual(result["physical_tile_ids"], ["UNKNOWN"] * 4)
        self.assertEqual(result["visible_face_count"], 3)
        self.assertEqual(result["action_kind"], "UNKNOWN")
        for field in ("safe_for_runtime", "safe_for_hint", "safe_for_executor",
                      "formal_promotion_evidence", "changes_runtime_behavior"):
            self.assertFalse(result[field])

    def test_group_constraint_does_not_hide_disagreeing_visible_face(self):
        result = self.rank({
            "top": {"P6": .9, "P8": .1},
            "lower_left": {"P6": .9, "P8": .1},
            "lower_right": {"P6": .1, "P8": .9},
        })
        self.assertEqual(result["top_tile"], "P6")
        self.assertEqual(result["face_top1"]["lower_right"], "P8")
        self.assertFalse(result["visible_top1_agreement"])

    def test_sequence_is_not_silently_decoded_as_flat(self):
        result = self.rank(dict(zip(VISIBLE_ROLES, ({"P4": .9}, {"P5": .9}, {"P6": .9}))))
        self.assertIsNone(result["top_tile"])
        self.assertEqual(result["same_tile_hypotheses"], [])

    def test_review_or_source_missing_blocks_ranking(self):
        rows = {role: {"P6": .9} for role in VISIBLE_ROLES}
        for kwargs in ({"source_frame_verified": False}, {"visible_faces_reviewed": False}):
            self.assertIsNone(self.rank(rows, **kwargs)["top_tile"])

    def test_missing_extra_or_positional_roles_are_rejected(self):
        for roles in (("top", "lower_left"), (*VISIBLE_ROLES, "hidden"), ("0", "1", "2")):
            self.assertIsNone(self.rank({role: {"P6": .9} for role in roles})["top_tile"])

    def test_invalid_scores_and_ties_remain_ambiguous(self):
        invalid = {role: {"P6": float("nan"), "P8": True, "UNKNOWN": .9} for role in VISIBLE_ROLES}
        self.assertIsNone(self.rank(invalid)["top_tile"])
        tied = self.rank({role: {"P6": .9, "P8": .9} for role in VISIBLE_ROLES})
        self.assertFalse(tied["visible_top1_agreement"])
        self.assertEqual(tied["margin"], 0)

    def test_one_candidate_has_no_measured_margin(self):
        result = self.rank({role: {"P6": .9} for role in VISIBLE_ROLES})
        self.assertIsNone(result["margin"])
        self.assertIn("insufficient_competing_same_tile_hypotheses", result["issues"])
