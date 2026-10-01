import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROFILE = (
    ROOT
    / "references/vision/2026-10-01/opponent_meld_domain_profile_v0_1.json"
)
VISION = all(
    importlib.util.find_spec(name) is not None
    for name in ("PIL", "cv2", "numpy")
)


class OpponentMeldDomainProfileTests(unittest.TestCase):
    def test_tracked_profile_is_pending_and_fail_closed(self):
        from workspace.vision.opponent_meld_domain_transfer import (
            PENDING,
            describe_opponent_domain_profile,
            load_opponent_meld_domain_profile,
        )

        profile = load_opponent_meld_domain_profile(PROFILE)
        self.assertEqual(profile.status, PENDING)
        self.assertFalse(profile.ready)
        self.assertIsNone(profile.measured_source_face_size_px)
        report = describe_opponent_domain_profile(profile)
        self.assertFalse(report["safe_for_runtime"])
        self.assertFalse(report["safe_for_hint"])
        self.assertFalse(report["safe_for_executor"])

    def test_pending_profile_refuses_invented_dimensions(self):
        from workspace.vision.opponent_meld_domain_transfer import (
            load_opponent_meld_domain_profile,
        )

        payload = json.loads(PROFILE.read_text(encoding="utf-8"))
        payload["measured_source_face_size_px"] = [28, 48]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                ValueError,
                "pending profile cannot contain measured dimensions",
            ):
                load_opponent_meld_domain_profile(path)

    def test_measured_profile_requires_smaller_source_face(self):
        from workspace.vision.opponent_meld_domain_transfer import (
            MEASURED,
            load_opponent_meld_domain_profile,
        )

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
        from workspace.vision.opponent_meld_domain_transfer import (
            MEASURED,
            OpponentMeldDomainProfile,
        )

        return OpponentMeldDomainProfile(
            status=MEASURED,
            canonical_face_size=(56, 96),
            measured_source_face_size_px=(28, 48),
            measurement_source_review_id="opp_meld_test",
        )

    def test_pending_profile_cannot_render(self):
        from PIL import Image
        from workspace.vision.opponent_meld_domain_transfer import (
            load_opponent_meld_domain_profile,
            simulate_opponent_source_resolution_loss,
        )

        profile = load_opponent_meld_domain_profile(PROFILE)
        image = Image.new("RGB", (56, 96), "white")
        with self.assertRaisesRegex(ValueError, "not measured"):
            simulate_opponent_source_resolution_loss(image, profile)

    def test_measured_transform_is_deterministic_and_canonical_size(self):
        import numpy as np
        from PIL import Image, ImageDraw
        from workspace.vision.opponent_meld_domain_transfer import (
            simulate_opponent_source_resolution_loss,
        )

        image = Image.new("RGB", (56, 96), "white")
        draw = ImageDraw.Draw(image)
        for x in range(4, 52, 4):
            draw.line((x, 8, 55 - x // 2, 88), fill="black", width=1)

        profile = self._measured_profile()
        first = simulate_opponent_source_resolution_loss(image, profile)
        second = simulate_opponent_source_resolution_loss(image, profile)

        self.assertEqual(first.size, (56, 96))
        self.assertTrue(
            np.array_equal(np.asarray(first), np.asarray(second))
        )
        self.assertFalse(
            np.array_equal(np.asarray(image), np.asarray(first))
        )


if __name__ == "__main__":
    unittest.main()
