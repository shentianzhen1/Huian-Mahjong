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
from workspace.vision.capture_validator.auto_recorder import (
    AutoHandRecorder, FrameRingBuffer, HandPhase,
    PhaseDetection, TemplatePhaseDetector,
)
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
            metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["frames"], 10)
            self.assertEqual(metadata["stop_reason"], "test complete")
            self.assertIn("start_time", metadata)
            self.assertIn("end_time", metadata)
            self.assertEqual(metadata["detected_phases"], [])

    def test_long_and_manual_unlimited_durations(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Image.new("RGB", (160, 90), "green")
            long_recording = Recorder(directory, image.size, {}, seconds=1800)
            self.assertFalse(long_recording.append(
                image, {}, long_recording.started
            ))
            long_path = long_recording.close("long manual stop")
            unlimited = Recorder(directory, image.size, {}, seconds=None)
            try:
                self.assertFalse(unlimited.append(
                    image, {}, unlimited.started + 1
                ))
            finally:
                unlimited_path = unlimited.close("manual unlimited stop")
            self.assertNotEqual(long_path, unlimited_path)
            long_meta = json.loads(
                long_path.with_suffix(".json").read_text(encoding="utf-8")
            )
            unlimited_meta = json.loads(
                unlimited_path.with_suffix(".json").read_text(encoding="utf-8")
            )
            self.assertEqual(long_meta["duration_limit_seconds"], 1800)
            self.assertIsNone(unlimited_meta["duration_limit_seconds"])

    def test_ring_buffer_keeps_only_last_ten_seconds(self):
        ring = FrameRingBuffer(seconds=10)
        image = Image.new("RGB", (32, 18), "blue")
        for second in range(13):
            ring.append(
                image, {"sequence": second}, second, 1000 + second
            )
        buffered = ring.snapshot()
        self.assertEqual(buffered[0].monotonic, 2)
        self.assertEqual(buffered[-1].monotonic, 12)
        self.assertEqual(buffered[-1].image().size, image.size)

    def test_fixed_roi_template_detector(self):
        with tempfile.TemporaryDirectory() as directory:
            opening = Image.new("RGB", (160, 90), "black")
            settlement = Image.new("RGB", (160, 90), "black")
            opening_pixels = np.asarray(opening).copy()
            settlement_pixels = np.asarray(settlement).copy()
            opening_pixels[10:70:4, 20:140] = 255
            settlement_pixels[10:70, 20:140:4] = 255
            opening = Image.fromarray(opening_pixels)
            settlement = Image.fromarray(settlement_pixels)
            opening_path = Path(directory) / "opening.png"
            settlement_path = Path(directory) / "settlement.png"
            opening.save(opening_path)
            settlement.save(settlement_path)
            detector = TemplatePhaseDetector({
                "OPENING": [opening_path],
                "SETTLEMENT": [settlement_path],
            }, threshold=.9)
            self.assertEqual(detector.detect(opening).phase, "OPENING")
            self.assertEqual(
                detector.detect(settlement).phase, "SETTLEMENT"
            )

    def test_auto_hand_recorder_state_machine_and_independent_files(self):
        class SequenceDetector:
            def __init__(self, phases):
                self.phases = iter(phases)

            def detect(self, _image):
                phase = next(self.phases)
                return PhaseDetection(
                    phase, 0.99 if phase else 0.20, "test_feature"
                )

        phases = (
            [None, None, "OPENING", "OPENING", None, None,
             "SETTLEMENT", "SETTLEMENT", None]
            + ["OPENING", "OPENING", None, None,
               "SETTLEMENT", "SETTLEMENT", None]
        )
        with tempfile.TemporaryDirectory() as directory:
            automatic = AutoHandRecorder(
                directory, lambda: {"backend": "TEST"},
                SequenceDetector(phases), fps=2,
                pre_roll_seconds=10, post_roll_seconds=.5,
                confirm_frames=2,
            )
            image = Image.new("RGB", (160, 90), "green")
            completed = []
            for index in range(len(phases)):
                path = automatic.process(
                    image, {"sequence": index},
                    index * .5, 1000 + index * .5
                )
                if path:
                    completed.append(path)
            self.assertEqual(len(completed), 2)
            self.assertNotEqual(completed[0], completed[1])
            self.assertEqual(automatic.state, HandPhase.WAITING)
            for path in completed:
                self.assertTrue(path.exists())
                self.assertTrue(path.with_suffix(".json").exists())
                self.assertTrue(path.with_suffix(".jsonl").exists())
                metadata = json.loads(
                    path.with_suffix(".json").read_text(encoding="utf-8")
                )
                self.assertTrue(metadata["hand_id"])
                self.assertEqual(
                    [row["phase"] for row in metadata["detected_phases"]],
                    ["OPENING", "PLAYING", "SETTLEMENT"],
                )
                self.assertEqual(
                    metadata["stop_reason"],
                    "检测到结算页并完成 5 秒后录制",
                )

    def test_uncertain_detection_never_auto_stops_active_hand(self):
        class Detector:
            def __init__(self):
                self.calls = 0

            def detect(self, _image):
                self.calls += 1
                phase = "OPENING" if self.calls <= 2 else None
                return PhaseDetection(phase, .99 if phase else .4)

        with tempfile.TemporaryDirectory() as directory:
            automatic = AutoHandRecorder(
                directory, lambda: {}, Detector(), fps=2,
                pre_roll_seconds=10, post_roll_seconds=.5,
                confirm_frames=2,
            )
            image = Image.new("RGB", (160, 90), "green")
            for index in range(8):
                self.assertIsNone(automatic.process(
                    image, {}, index * .5, 1000 + index * .5
                ))
            self.assertIsNotNone(automatic.recorder)
            self.assertEqual(automatic.state, HandPhase.PLAYING)
            path = automatic.close("test cleanup")
            self.assertTrue(path.exists())

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

