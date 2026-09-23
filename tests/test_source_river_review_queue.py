"""Review-queue safety tests; never include private original video in CI."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

AVAILABLE = all(importlib.util.find_spec(n) is not None for n in ("cv2", "numpy", "PIL"))


@unittest.skipUnless(AVAILABLE, "Vision dependencies are optional")
class ReviewQueueTests(unittest.TestCase):
    def setUp(self):
        import cv2
        import numpy as np
        self.cv2, self.np = cv2, np
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.video = self.root / "synthetic.mp4"
        self.video.write_bytes(b"synthetic, no private pixel data")
        self.sha = hashlib.sha256(self.video.read_bytes()).hexdigest()
        self.manifest = self.root / "manifest.json"
        self.manifest.write_text(json.dumps({
            "schema_version": "source_river_geometry_v0_1",
            "source_session": "synthetic_review",
            "source_sha256": self.sha,
            "frame_size": [1046, 480],
            "development_only": True,
            "excluded_from_formal_promotion": True,
            "zones": [
                {"actor": "opponent", "bbox": [.56, .218, .11, .087],
                 "single_width": [.024, .03], "single_height": [.058, .07]},
                {"actor": "player", "bbox": [.297, .519, .125, .083],
                 "single_width": [.029, .037], "single_height": [.05, .066]},
            ],
        }), encoding="utf-8")

    def capture(self):
        cv2, np = self.cv2, self.np

        class FakeCapture:
            def __init__(self):
                self.i = 0
                self.last = -1
                self.released = False
            def isOpened(self):
                return True
            def get(self, prop):
                if prop == cv2.CAP_PROP_FRAME_COUNT:
                    return 14
                if prop == cv2.CAP_PROP_FRAME_WIDTH:
                    return 1046
                if prop == cv2.CAP_PROP_FRAME_HEIGHT:
                    return 480
                if prop == cv2.CAP_PROP_POS_MSEC:
                    return (self.last + 1) * (1000 / 30)
                raise AssertionError(prop)
            def set(self, prop, value):
                self.i = int(value)
                return prop == cv2.CAP_PROP_POS_FRAMES
            def read(self):
                if self.i >= 14:
                    return False, None
                index = self.i
                self.last = index
                self.i += 1
                image = np.zeros((480, 1046, 3), dtype=np.uint8)
                image[:] = (23, 67, 47)
                if index >= 5:
                    image[110:140, 646:674] = 237
                image[45:75, 646:674] = 237  # hand negative
                image[170:240, 480:540] = 237  # zoom negative
                return True, cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            def release(self):
                self.released = True
        return FakeCapture()

    def test_private_unknown_only_one_stable_crop(self):
        from workspace.vision.source_river_review_queue import export_review_queue
        fake = self.capture()
        out = self.root / "private_queue"
        with patch.object(self.cv2, "VideoCapture", return_value=fake):
            result = export_review_queue(self.video, manifest_path=self.manifest,
                                         first_frame=0, last_frame=13, output_dir=out)
        self.assertTrue(fake.released)
        self.assertEqual(len(result["candidates"]), 1)
        row = result["candidates"][0]
        self.assertEqual(row["screen_side_actor"], "opponent")
        self.assertTrue(all(row[key] is None for key in ("tile_id", "turn_actor", "action_kind")))
        self.assertEqual(row["review_status"], "pending")
        self.assertFalse(result["formal_promotion_evidence"])
        self.assertFalse(result["safe_for_executor"])
        self.assertEqual(hashlib.sha256((out / row["crop_file"]).read_bytes()).hexdigest(), row["crop_sha256"])
        self.assertEqual(json.loads((out / "review_queue.json").read_text())["candidates"], result["candidates"])

    def test_wrong_source_aborts_before_video_capture(self):
        from workspace.vision.source_river_review_queue import export_review_queue
        self.video.write_bytes(b"mutated")
        with patch.object(self.cv2, "VideoCapture", side_effect=AssertionError("should not decode")):
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                export_review_queue(self.video, manifest_path=self.manifest,
                                    first_frame=0, last_frame=13,
                                    output_dir=self.root / "private_queue")

    def test_source_reviewed_span_rejects_unreviewed_frames(self):
        from workspace.vision.source_river_review_queue import export_review_queue
        data = json.loads(self.manifest.read_text())
        data["reviewed_frame_span"] = [5, 10]
        self.manifest.write_text(json.dumps(data))
        with patch.object(self.cv2, "VideoCapture", side_effect=AssertionError("no decode")):
            with self.assertRaisesRegex(ValueError, "source-reviewed river interval"):
                export_review_queue(self.video, manifest_path=self.manifest,
                                    first_frame=0, last_frame=13,
                                    output_dir=self.root / "private_queue")

    def test_private_output_guard_and_no_overwrite(self):
        from workspace.vision.source_river_review_queue import export_review_queue
        with self.assertRaisesRegex(ValueError, "outside repository"):
            export_review_queue(self.video, manifest_path=self.manifest,
                                first_frame=0, last_frame=13,
                                output_dir=Path(__file__).resolve().parents[1] / "private_unsafe")
        out = self.root / "private_queue"
        out.mkdir()
        (out / "existing.txt").write_text("keep")
        with self.assertRaisesRegex(ValueError, "empty"):
            export_review_queue(self.video, manifest_path=self.manifest,
                                first_frame=0, last_frame=13, output_dir=out)
        self.assertEqual((out / "existing.txt").read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
