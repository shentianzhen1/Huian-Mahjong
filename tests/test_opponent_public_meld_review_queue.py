import copy
import json
from pathlib import Path
import unittest

from workspace.vision.opponent_public_meld_review_queue import (
    validate_opponent_public_meld_review_queue,
)


QUEUE = Path(
    "references/vision/2026-10-01/opponent_public_meld_review_queue_v0_1.json"
)


class OpponentPublicMeldReviewQueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(QUEUE.read_text(encoding="utf-8"))

    def test_tracked_queue_is_valid_and_not_runtime_evidence(self):
        result = validate_opponent_public_meld_review_queue(self.payload)
        self.assertTrue(result["valid"], result["issues"])
        self.assertEqual(result["queued_group_count"], 3)
        self.assertEqual(result["independent_match_group_count"], 2)
        self.assertEqual(result["source_verified_group_count"], 1)
        self.assertEqual(result["classifier_ready_group_count"], 1)
        self.assertFalse(result["safe_for_runtime"])
        self.assertFalse(result["safe_for_hint"])
        self.assertFalse(result["safe_for_executor"])

    def test_classifier_ready_group_has_locked_measurement_but_identity_unknown(self):
        row = self.payload["items"][0]
        self.assertEqual(row["crop_status"], "CLASSIFIER_READY")
        self.assertEqual(row["measured_source_face_size_px"], [22, 29])
        self.assertEqual(row["stable_measurement_crop_count"], 5)
        self.assertEqual(row["identity_runtime_status"], "UNKNOWN")

    def test_same_match_groups_are_not_counted_as_independent(self):
        payload = copy.deepcopy(self.payload)
        payload["current_counts"]["independent_original_match_groups"] = 3
        result = validate_opponent_public_meld_review_queue(payload)
        self.assertFalse(result["valid"])
        self.assertIn(
            "current_counts.independent_original_match_groups",
            result["issues"],
        )

    def test_invalid_nonsequence_truth_fails_closed(self):
        payload = copy.deepcopy(self.payload)
        payload["items"][0]["expected_tiles"] = ["M1", "M3", "M4"]
        result = validate_opponent_public_meld_review_queue(payload)
        self.assertFalse(result["valid"])
        self.assertIn("items[0].expected_tiles", result["issues"])

    def test_missing_exact_source_digest_is_rejected(self):
        payload = copy.deepcopy(self.payload)
        payload["items"][1].pop("source_sha256")
        result = validate_opponent_public_meld_review_queue(payload)
        self.assertFalse(result["valid"])
        self.assertIn("items[1].source_sha256", result["issues"])


if __name__ == "__main__":
    unittest.main()
