import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "references/vision/2026-10-01/opponent_meld_domain_profile_v0_1.json"
QUEUE = ROOT / "references/vision/2026-10-01/opponent_public_meld_review_queue_v0_1.json"
VISION = all(importlib.util.find_spec(name) is not None for name in ("PIL", "cv2", "numpy"))


class OpponentMeldDomainProfileTests(unittest.TestCase):
    def test_tracked_profile_is_measured_but_still_fail_closed(self):
        from workspace.vision.opponent_meld_domain_transfer import (
            MEASURED,
            describe_opponent_domain_profile,
            load_opponent_meld_domain_profile,
        )
        profile = load_opponent_meld_domain_profile(PROFILE)
        self.assertEqual(profile.status, MEASURED)
        self.assertTrue(profile.ready)
        self.assertEqual(profile.measured_source_face_size_px, (22, 29))
        self.assertEqual(profile.measurement_source_review_id, "opp_meld_14_m123")
        report = describe_opponent_domain_profile(profile)
        self.assertFalse(report["safe_for_runtime"])
        self.assertFalse(report["safe_for_hint"])
        self.assertFalse(report["safe_for_executor"])

    def test_tracked_profile_qualifies_against_review_queue(self):
        from workspace.vision.opponent_meld_domain_transfer import (
            load_opponent_meld_domain_profile,
            qualify_opponent_meld_domain_profile,
        )
        profile = load_opponent_meld_domain_profile(PROFILE)
        queue = json.loads(QUEUE.read_text(encoding="utf-8"))
        result = qualify_opponent_meld_domain_profile(profile, queue)
        self.assertTrue(result["qualified"])
        self.assertEqual(result["reason"], "measured_source_exact_verified_and_classifier_ready")
        self.assertFalse(result["safe_for_runtime"])
        self.assertFalse(result["safe_for_hint"])
        self.assertFalse(result["safe_for_executor"])

    def test_pending_profile_refuses_invented_dimensions(self):
        from workspace.vision.opponent_meld_domain_transfer import PENDING, load_opponent_meld_domain_profile
        payload = json.loads(PROFILE.read_text(encoding="utf-8"))
        payload["status"] = PENDING
        payload["measurement_source_review_id"] = None
        payload["measured_source_face_size_px"] = [28, 48]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "pending profile cannot contain measured dimensions"):
                load_opponent_meld_domain_profile(path)

    def test_pending_profile_cannot_qualify_against_review_queue(self):
        from workspace.vision.opponent_meld_domain_transfer import PENDING, OpponentMeldDomainProfile, qualify_opponent_meld_domain_profile
        profile = OpponentMeldDomainProfile(
            status=PENDING,
            canonical_face_size=(56, 96),
            measured_source_face_size_px=None,
            measurement_source_review_id=None,
        )
        queue = json.loads(QUEUE.read_text(encoding="utf-8"))
        result = qualify_opponent_meld_domain_profile(profile, queue)
        self.assertFalse(result["qualified"])
        self.assertEqual(result["reason"], "profile_pending_measurement")

    def test_measured_profile_still_needs_classifier_ready_queue_crop(self):
        from workspace.vision.opponent_meld_domain_transfer import MEASURED, OpponentMeldDomainProfile, qualify_opponent_meld_domain_profile
        queue = json.loads(QUEUE.read_text(encoding="utf-8"))
        queue["items"][0]["crop_status"] = "SOURCE_VERIFIED_PENDING_EXACT_TOP_GROUP_CROP"
        profile = OpponentMeldDomainProfile(
            status=MEASURED,
            canonical_face_size=(56, 96),
            measured_source_face_size_px=(22, 29),
            measurement_source_review_id="opp_meld_14_m123",
        )
        result = qualify_opponent_meld_domain_profile(profile, queue)
        self.assertFalse(result["qualified"])
        self.assertEqual(result["reason"], "measurement_source_crop_not_classifier_ready")

    def test_measured_profile_requires_smaller_source_face(self):
        from workspace.vision.opponent_meld_domain_transfer import MEASURED, load_opponent_meld_domain_profile
        payload = json.loads(PROFILE.read_text(encoding="utf-8"))
        payload["status"] = MEASURED
        payload["measurement_source_review_id"] = "opp_meld_test"
        payload["measured_source_face_size_px"] = [56, 96]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "smaller source face"):
                load_opponent_meld_domain_profile(path)


@unittest.skipUnless(VISION, "Pillow/OpenCV/numpy are optional in core-only installs")
class OpponentMeldDomainTransferVisionTests(unittest.TestCase):
    def _measured_profile(self):
        from workspace.vision.opponent_meld_domain_transfer import MEASURED, OpponentMeldDomainProfile
        return OpponentMeldDomainProfile(
            status=MEASURED,
            canonical_face_size=(56, 96),
            measured_source_face_size_px=(22, 29),
            measurement_source_review_id="opp_meld_14_m123",
        )

    def test_pending_profile_cannot_render(self):
        from PIL import Image
        from workspace.vision.opponent_meld_domain_transfer import PENDING, OpponentMeldDomainProfile, simulate_opponent_source_resolution_loss
        profile = OpponentMeldDomainProfile(
            status=PENDING,
            canonical_face_size=(56, 96),
            measured_source_face_size_px=None,
            measurement_source_review_id=None,
        )
        image = Image.new("RGB", (56, 96), "white")
        with self.assertRaisesRegex(ValueError, "not measured"):
            simulate_opponent_source_resolution_loss(image, profile)

    def test_measured_transform_is_deterministic_and_canonical_size(self):
        import numpy as np
        from PIL import Image, ImageDraw
        from workspace.vision.opponent_meld_domain_transfer import simulate_opponent_source_resolution_loss
        image = Image.new("RGB", (56, 96), "white")
        draw = ImageDraw.Draw(image)
        for x in range(4, 52, 4):
            draw.line((x, 8, 55 - x // 2, 88), fill="black", width=1)
        profile = self._measured_profile()
        first = simulate_opponent_source_resolution_loss(image, profile)
        second = simulate_opponent_source_resolution_loss(image, profile)
        self.assertEqual(first.size, (56, 96))
        self.assertTrue(np.array_equal(np.asarray(first), np.asarray(second)))
        self.assertFalse(np.array_equal(np.asarray(image), np.asarray(first)))


if __name__ == "__main__":
    unittest.main()
