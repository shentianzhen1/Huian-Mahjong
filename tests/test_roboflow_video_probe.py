"""Synthetic-video regressions: no API key, no user's footage, no network."""
from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from workspace.vision.roboflow_video_probe import (
    normalized_roi, parse_indices, trial_video,
)

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None


@unittest.skipIf(cv2 is None or np is None, "opencv/numpy are optional Vision extras")
class RoboflowVideoTrialTests(unittest.TestCase):
    def synthetic(self, folder: Path) -> tuple[Path, str]:
        file = folder / "synthetic.avi"
        writer = cv2.VideoWriter(str(file), cv2.VideoWriter_fourcc(*"MJPG"),
                                 10.0, (128, 96))
        self.assertTrue(writer.isOpened())
        for index in range(7):
            writer.write(np.full((96, 128, 3), index * 30, dtype=np.uint8))
        writer.release()
        return file, hashlib.sha256(file.read_bytes()).hexdigest()

    def test_preflight_reads_exact_hashed_video_and_never_uploads(self):
        with TemporaryDirectory() as temp:
            video, digest = self.synthetic(Path(temp))
            calls = []
            report = trial_video(video, expected_sha256=digest,
                                 source_group="synthetic_match",
                                 frames=[1, 3, 5],
                                 private_frames_dir=Path(temp) / "private")
            self.assertEqual(report["mode"], "offline_video_preflight")
            self.assertEqual([f["frame"] for f in report["sampled_frames"]], [1, 3, 5])
            self.assertEqual(report["model_calls"], 0)
            self.assertIsNone(report["recognition_accuracy"])
            self.assertFalse(report["safe_for_executor"])
            self.assertEqual(len(list((Path(temp) / "private").glob("*.jpg"))), 3)
            self.assertEqual(calls, [])

    def test_fake_cloud_maps_tile_and_source_roi_without_precision_claim(self):
        with TemporaryDirectory() as temp:
            video, digest = self.synthetic(Path(temp))
            supplied = []
            def fake_infer(image_path):
                supplied.append(Path(image_path).is_file())
                return {"image": {"width": 64, "height": 48},
                        "predictions": [
                            {"class": "7C", "confidence": 0.95,
                             "x": 10, "y": 12, "width": 10, "height": 12},
                            {"class": "1S", "confidence": 0.81,
                             "x": 25, "y": 12, "width": 10, "height": 12},
                        ]}
            result = trial_video(
                video, expected_sha256=digest, source_group="synthetic_match",
                frames=[1, 2], roi=(.25, .25, .5, .5), infer=fake_infer,
            )
            self.assertEqual(supplied, [True, True])
            self.assertEqual(result["model_calls"], 2)
            self.assertEqual(result["total_detections"], 4)
            self.assertEqual(result["unmapped_source_classes"], {"1S": 2})
            item = result["sampled_frames"][0]["detections"][0]
            self.assertEqual(item["tile_id"], "M7")
            self.assertGreaterEqual(item["bbox"][0], 0.25)
            self.assertLessEqual(item["bbox"][0] + item["bbox"][2], 0.75)
            self.assertIsNone(result["recognition_accuracy"])
            self.assertFalse(result["runtime_identity_ready"])

    def test_wrong_source_and_out_of_bounds_rejected(self):
        with TemporaryDirectory() as temp:
            video, digest = self.synthetic(Path(temp))
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                trial_video(video, expected_sha256="a" * 64,
                            source_group="a", frames=[1])
            with self.assertRaisesRegex(ValueError, "outside source recording"):
                trial_video(video, expected_sha256=digest,
                            source_group="a", frames=[7])
            with self.assertRaisesRegex(ValueError, "source"):
                trial_video(video, expected_sha256=digest,
                            source_group=" ", frames=[1])

    def test_input_validation(self):
        self.assertEqual(parse_indices("4,2,0"), [0, 2, 4])
        self.assertEqual(normalized_roi("0.2,0.3,0.4,0.5"), (.2, .3, .4, .5))
        for case in ("", "-1", "1,1", "1,invalid"):
            with self.assertRaises(ValueError):
                parse_indices(case)
        for case in ("nan,0,.5,.5", "-.1,0,.5,.5",
                     "0,0,.5,1.2", "0,.2,0,.2"):
            with self.assertRaises(ValueError):
                normalized_roi(case)


if __name__ == "__main__":
    unittest.main()
