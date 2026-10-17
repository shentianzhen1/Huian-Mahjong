from __future__ import annotations

import unittest

from workspace.vision.public_meld_group_identity_decoder import (
    rank_regular_public_meld_identity,
)


class PublicMeldGroupIdentityDecoderTests(unittest.TestCase):
    def test_sequence_context_corrects_one_bad_individual_top1(self):
        result = rank_regular_public_meld_identity(
            (
                {"P4": 0.90, "P6": 0.20},
                {"P5": 0.92, "P7": 0.30},
                {"P8": 0.95, "P6": 0.80, "P3": 0.10},
            ),
            minimum_group_margin=0.05,
        )
        self.assertEqual(result.top_tiles, ("P4", "P5", "P6"))
        self.assertEqual(result.development_proposal_tiles, ("P4", "P5", "P6"))
        report = result.to_dict()
        self.assertFalse(report["safe_for_runtime"])
        self.assertFalse(report["safe_for_executor"])
        self.assertEqual(report["action_kind"], "UNKNOWN")

    def test_triplet_is_valid_without_action_inference(self):
        result = rank_regular_public_meld_identity(
            (
                {"P1": 0.9, "P2": 0.2},
                {"P1": 0.88, "P2": 0.3},
                {"P1": 0.91, "P2": 0.4},
            ),
            minimum_group_margin=0.01,
        )
        self.assertEqual(result.top_tiles, ("P1", "P1", "P1"))
        self.assertEqual(result.development_proposal_tiles, ("P1", "P1", "P1"))
        self.assertIn(
            "development_group_identity_margin_passed",
            result.issues,
        )

    def test_low_margin_ambiguous_valid_sequences_abstain(self):
        result = rank_regular_public_meld_identity(
            (
                {"M1": 0.81, "M5": 0.80},
                {"M2": 0.81, "M6": 0.80},
                {"M3": 0.81, "M7": 0.80},
            ),
            minimum_group_margin=0.05,
        )
        self.assertEqual(result.top_tiles, ("M1", "M2", "M3"))
        self.assertIsNone(result.development_proposal_tiles)
        self.assertIn(
            "development_group_identity_margin_too_small",
            result.issues,
        )

    def test_ranking_only_mode_never_proposes(self):
        result = rank_regular_public_meld_identity(
            (
                {"S4": 0.9},
                {"S5": 0.9},
                {"S6": 0.9},
            )
        )
        self.assertEqual(result.top_tiles, ("S4", "S5", "S6"))
        self.assertIsNone(result.development_proposal_tiles)
        self.assertIn("development_margin_gate_not_configured", result.issues)

    def test_invalid_or_incomplete_inputs_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "exactly 3"):
            rank_regular_public_meld_identity(({"P1": 1.0},))

        result = rank_regular_public_meld_identity(
            (
                {"UNKNOWN": 1.0},
                {"P1": 1.0},
                {"P1": 1.0},
            ),
            minimum_group_margin=0.0,
        )
        self.assertIsNone(result.top_tiles)
        self.assertIn("face_0_has_no_valid_identity_scores", result.issues)


if __name__ == "__main__":
    unittest.main()
