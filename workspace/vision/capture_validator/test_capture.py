import inspect
import json
from pathlib import Path
import queue
import tempfile
import unittest

import cv2
import numpy as np
from PIL import Image
from windows_capture import Frame, WindowsCapture

from workspace.vision.capture_validator.backend import offer, wgc_frame_to_image
from workspace.vision.capture_validator.media import FrameHealth, Recorder, snapshot


class CaptureTests(unittest.TestCase):
    def test_installed_wgc_supports_exact_hwnd(self):
        self.assertIn("window_hwnd", inspect.signature(WindowsCapture).parameters)

    def test_installed_wgc_frame_converts_bgra_to_rgb(self):
        buffer = np.array([[[10, 20, 30, 0], [40, 50, 60, 255]]], dtype=np.uint8)
        image = wgc_frame_to_image(Frame(buffer, 2, 1, 0))
        self.assertEqual(image.mode, "RGB")
        self.assertEqual(image.size, (2, 1))
        self.assertEqual(image.tobytes(), bytes([30, 20, 10, 60, 50, 40]))

    def test_wgc_padded_rows_are_copied_before_buffer_reuse(self):
        raw = np.full((2, 16), 255, dtype=np.uint8)
        buffer = raw[:, :8].reshape(2, 2, 4)
        buffer[:] = [[[1, 2, 3, 0], [4, 5, 6, 255]],
                     [[7, 8, 9, 128], [10, 11, 12, 255]]]
        self.assertFalse(buffer.flags.c_contiguous)
        image = wgc_frame_to_image(Frame(buffer, 2, 2, 0))
        raw[:] = 0
        self.assertEqual(image.tobytes(), bytes([3, 2, 1, 6, 5, 4, 9, 8, 7, 12, 11, 10]))

    def test_black_static_change_and_resize_are_distinct(self):
        health = FrameHealth()
        image = Image.new("RGB", (160, 90), "white")
        self.assertFalse(health.inspect(image, 0)["black"])
        self.assertEqual(health.inspect(image, 6)["unchanged_seconds"], 6)
        dark = health.inspect(Image.new("RGB", (160, 90), "black"), 7)
        self.assertTrue(dark["black"])
        self.assertEqual(dark["unchanged_seconds"], 0)
        resized = health.inspect(Image.new("RGB", (320, 180), "white"), 8)
        self.assertTrue(resized["resized"])
        self.assertEqual(resized["unchanged_seconds"], 0)

    def test_queue_is_bounded(self):
        out = queue.Queue(maxsize=1)
        offer(out, ("frame", 1))
        offer(out, ("frame", 2))
        self.assertEqual(out.qsize(), 1)

    def test_screenshot_roundtrip_and_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Image.new("RGB", (160, 90), (12, 45, 89))
            path = snapshot(image, directory, {"backend": "SYNTHETIC", "sequence": 7})
            with Image.open(path) as restored:
                self.assertEqual(restored.tobytes(), image.tobytes())
            self.assertEqual(json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))["sequence"], 7)
            self.assertNotEqual(path, snapshot(image, directory, {}))

    def test_recording_decodes_and_records_duplicate_source(self):
        with tempfile.TemporaryDirectory() as directory:
            recording = Recorder(directory, (160, 90), {"synthetic": True}, seconds=1)
            image = Image.new("RGB", (160, 90), (20, 130, 70))
            self.assertTrue(recording.append(image, {"sequence": 1}, recording.started + 1))
            path = recording.close("test complete")
            self.assertEqual(recording.close(), path)
            cap = cv2.VideoCapture(str(path))
            frames = []
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                frames.append(frame.shape)
            cap.release()
            self.assertEqual(frames, [(90, 160, 3)] * 10)
            timeline = [json.loads(line) for line in path.with_suffix(".jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(timeline), 10)
            self.assertTrue(all(row["source"]["sequence"] == 1 for row in timeline))
            self.assertEqual(json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))["frames"], 10)

    def test_resize_and_large_delay_do_not_write_bad_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            recording = Recorder(directory, (160, 90), {}, seconds=10)
            try:
                with self.assertRaises(ValueError):
                    recording.append(Image.new("RGB", (320, 180)), {})
                with self.assertRaises(RuntimeError):
                    recording.append(Image.new("RGB", (160, 90)), {}, recording.started + 4)
                self.assertEqual(recording.frames, 0)
            finally:
                recording.close("rejected")

    def test_odd_dimensions_are_padded_without_losing_source_pixels(self):
        with tempfile.TemporaryDirectory() as directory:
            recording = Recorder(directory, (161, 91), {}, seconds=1)
            recording.append(Image.new("RGB", (161, 91), "green"), {}, recording.started)
            path = recording.close()
            cap = cv2.VideoCapture(str(path))
            ok, frame = cap.read()
            cap.release()
            self.assertTrue(ok)
            self.assertEqual(frame.shape[:2], (92, 162))
            metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["source_size"], [161, 91])


if __name__ == "__main__":
    unittest.main()

