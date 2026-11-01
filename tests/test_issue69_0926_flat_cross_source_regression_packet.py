from __future__ import annotations

import json
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
PACKET = REPO / "references/vision/2026-10-03/issue69_0926_flat_cross_source_regression_packet_v0_1.json"


class Issue690926FlatCrossSourceRegressionPacketTests(unittest.TestCase):
    def setUp(self):
        self.packet = json.loads(PACKET.read_text(encoding="utf-8"))

    def test_packet_is_fixed_and_same_match_excluded(self):
        self.assertEqual(self.packet["candidate_commit"], "69893a5c0ca18ccb3128b70ce9695fa48512f047")
        self.assertTrue(self.packet["same_match_references_excluded"])
        self.assertEqual(self.packet["total_groups"], 4)
        self.assertEqual(self.packet["total_visible_face_samples"], 60)
        self.assertEqual(
            [g["group_id"] for g in self.packet["groups"]],
            ["hand3_north", "hand3_bamboo1", "hand7_bamboo8", "hand8_wan9"],
        )

    def test_unsupported_classes_fail_closed_before_accuracy(self):
        self.assertEqual(self.packet["eligible_truth_classes_at_freeze"], [])
        self.assertEqual(
            self.packet["current_disposition"],
            "ELIGIBILITY_ABSTENTION_BEFORE_WEIGHTED_IDENTITY_SCORING",
        )
        result = self.packet["current_result"]
        self.assertEqual(result["correct"], 0)
        self.assertEqual(result["wrong"], 0)
        self.assertEqual(result["unknown_due_to_reference_coverage"], 60)
        self.assertFalse(result["accuracy_measured"])

    def test_runtime_remains_off(self):
        self.assertFalse(self.packet["runtime_integration"])
        self.assertFalse(self.packet["formal_promotion_evidence"])
        self.assertFalse(self.packet["safe_for_runtime"])
        self.assertFalse(self.packet["safe_for_hint"])
        self.assertFalse(self.packet["safe_for_executor"])


if __name__ == "__main__":
    unittest.main()
