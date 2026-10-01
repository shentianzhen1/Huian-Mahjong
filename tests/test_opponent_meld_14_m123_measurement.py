import hashlib
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "references/vision/2026-10-01/opponent_meld_14_m123_geometry_result_v0_1.json"
PROFILE = ROOT / "references/vision/2026-10-01/opponent_meld_domain_profile_v0_1.json"
QUEUE = ROOT / "references/vision/2026-10-01/opponent_public_meld_review_queue_v0_1.json"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
ASSET = ROOT / "references/vision/2026-10-01/opponent_meld_crops/opp_meld_14_m123_5frame_strip.webp"


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

    def test_only_privacy_bounded_lossless_strip_is_committed(self):
        from PIL import Image

        privacy = self.report["privacy"]
        self.assertFalse(privacy["raw_video_committed"])
        self.assertFalse(privacy["full_frame_committed"])
        self.assertTrue(privacy["derived_crop_pixels_committed"])
        self.assertFalse(privacy["player_or_room_metadata_published"])
        self.assertFalse(privacy["public_asset_contains_player_or_room_metadata"])

        asset = self.report["public_evaluation_asset"]
        self.assertEqual(asset["path"], ASSET.relative_to(ROOT).as_posix())
        self.assertEqual(asset["encoding"], "webp_lossless")
        self.assertTrue(asset["decoded_rgb_matches_original_png"])
        self.assertEqual(asset["frame_count"], 5)
        self.assertEqual(asset["frame_size_px"], [71, 33])
        self.assertFalse(asset["player_or_room_metadata"])
        self.assertEqual(hashlib.sha256(ASSET.read_bytes()).hexdigest(), asset["sha256"])
        with Image.open(ASSET) as source:
            rgb = source.convert("RGB")
        self.assertEqual(rgb.size, (71, 165))
        self.assertEqual(hashlib.sha256(rgb.tobytes()).hexdigest(), asset["decoded_rgb_sha256"])

        self.assertEqual(len(self.report["stable_samples"]), 5)
        for sample in self.report["stable_samples"]:
            self.assertTrue(SHA256.fullmatch(sample["sha256"]))
            self.assertGreater(sample["bytes"], 0)
            self.assertLess(sample["bytes"], 10_000)
            self.assertEqual(sample["crop_size_px"], [71, 33])
            self.assertEqual(sample["stack_state"], "FLAT")

    def test_profile_and_queue_use_same_measured_dimensions(self):
        self.assertEqual(self.profile["status"], "MEASURED_REAL_TOP_GROUP")
        self.assertEqual(self.profile["measurement_source_review_id"], "opp_meld_14_m123")
        self.assertEqual(self.profile["measured_source_face_size_px"], [22, 29])
        row = next(item for item in self.queue["items"] if item["review_id"] == "opp_meld_14_m123")
        self.assertEqual(row["crop_status"], "CLASSIFIER_READY")
        self.assertEqual(row["measured_source_face_size_px"], [22, 29])
        self.assertEqual(row["stable_measurement_crop_count"], 5)
        self.assertEqual(row["measurement_crop_storage"], "PUBLIC_TILE_ONLY_5FRAME_STRIP_NO_PLAYER_OR_ROOM_METADATA")
        self.assertEqual(row["public_evaluation_asset"]["sha256"], "d6122210ebb2f5c230ecb08ac35c205824495695341a938831ded2f156fe81f9")
        self.assertEqual(row["identity_runtime_status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
