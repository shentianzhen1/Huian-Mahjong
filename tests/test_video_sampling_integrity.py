from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

from workspace.hint_alpha.video_test import iter_video_samples


class Capture:
    def __init__(self, fail_at=None, retrieve_failure=False):
        self.index = -1
        self.fail_at = fail_at
        self.retrieve_failure = retrieve_failure
        self.released = False
        self.seek_calls = []

    def set(self, prop, value):
        self.seek_calls.append(value)
        self.index = value - 1
        return True

    def grab(self):
        self.index += 1
        return self.index != self.fail_at

    def retrieve(self):
        return not self.retrieve_failure, self.index

    def get(self, prop):
        return self.index * 100.0

    def release(self):
        self.released = True


class VideoSamplingIntegrityTests(unittest.TestCase):
    def samples(self, capture, **kwargs):
        cv = SimpleNamespace(VideoCapture=lambda path: capture,
                             CAP_PROP_POS_FRAMES=1, CAP_PROP_POS_MSEC=2,
                             COLOR_BGR2RGB=3, cvtColor=lambda frame, mode: frame)
        pil = SimpleNamespace(Image=SimpleNamespace(fromarray=lambda value: value))
        with patch.dict(sys.modules, {"cv2": cv, "PIL": pil}), patch(
            "workspace.hint_alpha.video_test.probe_video",
            return_value={"fps": 10.0, "frame_count": 30, "duration_seconds": 3.0},
        ):
            return list(iter_video_samples("synthetic.mp4", sample_interval_seconds=.1, **kwargs))

    def test_nonzero_start_has_exact_sequential_ordinals(self):
        cap = Capture()
        result = self.samples(cap, start_seconds=1.0, duration_seconds=.3)
        self.assertEqual(cap.seek_calls, [])
        self.assertEqual([row[0] for row in result], [10, 11, 12])
        self.assertEqual([row[2] for row in result], [10, 11, 12])
        self.assertTrue(cap.released)

    def test_premature_end_cannot_be_reported_as_complete(self):
        cap = Capture(fail_at=15)
        with self.assertRaisesRegex(ValueError, "frame 15"):
            self.samples(cap)
        self.assertTrue(cap.released)

    def test_failure_before_start_is_not_skipped(self):
        cap = Capture(fail_at=5)
        with self.assertRaisesRegex(ValueError, "frame 5"):
            self.samples(cap, start_seconds=1.0)
        self.assertTrue(cap.released)

    def test_retrieve_failure_is_explicit(self):
        cap = Capture(retrieve_failure=True)
        with self.assertRaisesRegex(ValueError, "frame 0"):
            self.samples(cap)
        self.assertTrue(cap.released)

    def test_natural_end_is_successful(self):
        cap = Capture()
        self.assertEqual(len(self.samples(cap)), 30)
        self.assertTrue(cap.released)

    def test_out_of_range_start_does_not_clamp_to_last_frame(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            self.samples(Capture(), start_seconds=4.0)

    def test_user_stop_is_not_a_decode_failure(self):
        cap = Capture(fail_at=0)
        self.assertEqual(self.samples(cap, stop_event=SimpleNamespace(is_set=lambda: True)), [])
        self.assertTrue(cap.released)
