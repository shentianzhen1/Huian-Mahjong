import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "references/vision/2026-10-01/opponent_meld_14_m123_geometry_result_v0_1.json"
PROFILE = ROOT / "references/vision/2026-10-01/opponent_meld_domain_profile_v0_1.json"
QUEUE = ROOT / "references/vision/2026-10-01/opponent_public_meld_review_queue_v0_1.json"
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class OpponentMeldM123MeasurementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))
        cls.profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        cls.queue = json.loads(QUEUE.read_text(encoding="utf-8"))

    def test_measurement_is_real_stable_flat_geometry_only(self):
        aggregate = self.report["aggregate"]
        self.assertEqual(aggregate["stable_sample_count"], 5)
        self.assertTrue(aggregate["all_same_group_bbox"])
        self.assertTrue(aggregate["all_flat"])
        self.assertTrue(aggregate["all_classifier_ready_three_face_geometry"])
        self.assertEqual(aggregate["tight_group_size_px"], [67, 29])
        self.assertEqual(aggregate["effective_source_face_widths_px"], [22, 23, 22])
        self.assertEqual(aggregate["representative_source_face_size_px"], [22, 29])
        self.assertEqual(self.report["identity_runtime_status"], "UNKNOWN")
        self.assertEqual(self.report["runtime_identity_threshold_unchanged"], 0.82)
        self.assertFalse(self.report["safe_for_runtime"])
        self.assertFalse(self.report["safe_for_hint"])
        self.assertFalse(self.report["safe_for_executor"])

    def test_private_pixels_are_not_committed_and_crop_hashes_are_locked(self):
        privacy = self.report["privacy"]
        self.assertFalse(privacy["raw_video_committed"])
        self.assertFalse(privacy["full_frame_committed"])
        self.assertFalse(privacy["derived_crop_pixels_committed"])
        self.assertFalse(privacy["player_or_room_metadata_published"])
        self.assertEqual(
            self.report["evidence_storage"],
            "PUBLIC_METADATA_ONLY_PRIVATE_PIXELS_RETAINED_OUTSIDE_REPOSITORY",
        )
        self.assertEqual(len(self.report["stable_samples"]), 5)
        for row in self.report["stable_samples"]:
            self.assertTrue(SHA256.fullmatch(row["sha256"]))
            self.assertGreater(row["bytes"], 0)
            self.assertLess(row["bytes"], 10_000)
            self.assertEqual(row["crop_size_px"], [71, 33])
            self.assertEqual(row["stack_state"], "FLAT")

    def test_profile_and_queue_use_same_measured_dimensions(self):
        self.assertEqual(self.profile["status"], "MEASURED_REAL_TOP_GROUP")
        self.assertEqual(self.profile["measurement_source_review_id"], "opp_meld_14_m123")
        self.assertEqual(self.profile["measured_source_face_size_px"], [22, 29])
        row = next(item for item in self.queue["items"] if item["review_id"] == "opp_meld_14_m123")
        self.assertEqual(row["crop_status"], "CLASSIFIER_READY")
        self.assertEqual(row["measured_source_face_size_px"], [22, 29])
        self.assertEqual(row["stable_measurement_crop_count"], 5)
        self.assertEqual(
            row["measurement_crop_storage"],
            "PRIVATE_ONLY_TILE_BOUNDED_CROPS_NOT_COMMITTED",
        )
        self.assertEqual(row["identity_runtime_status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
