import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from workspace.hint_alpha.video_test import (REPLAY_OCR_INTERVAL_SECONDS, VideoTimelineAccumulator, automatic_sample_interval, build_video_timeline, render_video_timeline, render_video_timeline_event, run_video_test, summarize_video_test)
from workspace.vision.tiles_v0_1.public_state import PublicStateObservation





class AutomaticVideoParameterTests(unittest.TestCase):
    def test_short_match_uses_point_three_seconds(self):
        meta = {"fps": 60.0, "duration_seconds": 600.0}
        self.assertAlmostEqual(automatic_sample_interval(meta), 0.3, places=6)

    def test_longer_match_stays_inside_temporal_window(self):
        medium = {"fps": 30.0, "duration_seconds": 1200.0}
        long = {"fps": 60.0, "duration_seconds": 2400.0}
        self.assertLessEqual(automatic_sample_interval(medium) * 2, 0.8)
        self.assertLessEqual(automatic_sample_interval(long) * 2, 0.8)
        self.assertAlmostEqual(automatic_sample_interval(medium), 0.3, places=6)
        self.assertAlmostEqual(automatic_sample_interval(long), 0.3, places=6)

class VideoTestSummaryTests(unittest.TestCase):
    def test_summary_is_development_only_and_keeps_unknowns_explicit(self):
        runtime_rows = [
            {
                "display_allowed": True,
                "frames": [1, 2, 3],
                "source_seconds": [0.0, 0.2, 0.4],
                "snapshot": {
                    "hand_trusted": True,
                    "own_hand": ["M1"] * 16,
                    "gold_trusted": True,
                    "gold_tile": "M6",
                },
                "hint": {"phase": "PRE_DRAW", "best_discards": [], "issues": []},
            },
            {
                "display_allowed": False,
                "frames": [2, 3, 4],
                "source_seconds": [0.2, 0.4, 0.6],
                "snapshot": {
                    "hand_trusted": False,
                    "own_hand": [],
                    "gold_trusted": False,
                    "gold_tile": None,
                },
                "hint": {"phase": None, "best_discards": [], "issues": ["hand_untrusted"]},
            },
        ]
        public_rows = [
            {
                "observation": {
                    "hand_number": 1,
                    "score_pair": [1000, 1000],
                    "issues": [],
                }
            },
            {"error": "OCRUnavailable: tesseract missing"},
        ]
        result = summarize_video_test(
            runtime_rows,
            public_rows,
            {"width": 2796, "height": 1290},
        )
        self.assertFalse(result["formal_promotion_evidence"])
        self.assertFalse(result["windows_capture_validated"])
        self.assertFalse(result["safe_for_executor"])
        self.assertEqual(result["runtime"]["accepted_windows"], 1)
        self.assertEqual(result["runtime"]["blocked_windows"], 1)
        self.assertEqual(result["runtime"]["gold_tile_votes"], {"M6": 1})
        self.assertEqual(result["public_state"]["hand_number_votes"], {"1": 1})
        self.assertEqual(result["public_state"]["error_windows"], 1)


class VideoTimelineDraftTests(unittest.TestCase):
    def test_builds_only_observed_high_level_events_and_stays_partial(self):
        runtime_rows = [
            {
                "source_seconds": [0.0, 0.2, 0.4],
                "snapshot": {
                    "hand_trusted": True,
                    "own_hand": ["M1", "M2", "M3"],
                    "gold_trusted": True,
                    "gold_tile": "P6",
                },
                "hint": {"phase": "PRE_DRAW"},
            },
            {
                "source_seconds": [0.2, 0.4, 0.6],
                "snapshot": {
                    "hand_trusted": True,
                    "own_hand": ["M1", "M2", "M3"],
                    "gold_trusted": True,
                    "gold_tile": "P6",
                },
                "hint": {"phase": "PRE_DRAW"},
            },
            {
                "source_seconds": [10.0, 10.2, 10.4],
                "snapshot": {
                    "hand_trusted": True,
                    "own_hand": ["M1", "M2", "P3"],
                    "gold_trusted": True,
                    "gold_tile": "S2",
                },
                "hint": {"phase": "POST_DRAW"},
            },
        ]
        public_rows = [
            {"observation": {"hand_number": 1, "score_pair": [1000, 1000], "issues": []}},
            {"observation": {"hand_number": 1, "score_pair": [1000, 1000], "issues": []}},
            {"observation": {"hand_number": 2, "score_pair": [900, 1100], "issues": []}},
        ]
        source = {"sha256": "a" * 64, "session": "video-a"}
        timeline = build_video_timeline(runtime_rows, public_rows, source)
        kinds = [event["kind"] for event in timeline["events"]]
        self.assertEqual(
            kinds,
            [
                "HAND_START",
                "SCORE_BASELINE",
                "OPEN_GOLD",
                "PLAYER_HAND_SNAPSHOT",
                "HAND_START",
                "SETTLEMENT_SCORE_CHANGE",
                "OPEN_GOLD",
                "PLAYER_HAND_SNAPSHOT",
            ],
        )
        self.assertEqual(timeline["status"], "PARTIAL")
        self.assertFalse(timeline["public_actions_complete"])
        self.assertFalse(timeline["safe_for_executor"])
        text = "\n".join(render_video_timeline(timeline))
        self.assertIn("第1/8局开始", text)
        self.assertIn("开金：六筒", text)
        self.assertIn("结算方式 UNKNOWN", text)
        self.assertIn("流水状态：PARTIAL", text)


class IncrementalTimelineTests(unittest.TestCase):
    def test_observe_returns_only_new_lines_for_live_ui(self):
        source = {"sha256": "a" * 64, "session": "video-a"}
        acc = VideoTimelineAccumulator(source)
        runtime = {
            "source_seconds": [0.0, 0.2, 0.4],
            "snapshot": {
                "hand_trusted": True,
                "own_hand": ["M1", "M2", "M3"],
                "gold_trusted": True,
                "gold_tile": "P6",
            },
            "hint": {"phase": "PRE_DRAW"},
        }
        public = {
            "observation": {
                "hand_number": 1,
                "score_pair": [1000, 1000],
                "issues": [],
            }
        }
        created = acc.observe(runtime, public)
        self.assertEqual(
            [event["kind"] for event in created],
            ["HAND_START", "SCORE_BASELINE", "OPEN_GOLD", "PLAYER_HAND_SNAPSHOT"],
        )
        self.assertIn("第1/8局开始", render_video_timeline_event(created[0]))
        self.assertEqual(acc.observe(runtime, public), ())


class ReplayOcrCadenceTests(unittest.TestCase):
    def test_reuses_public_state_between_sparse_ocr_samples(self):
        samples = [
            (index, index * 0.2, object())
            for index in range(1, 9)
        ]

        def runtime_row(samples, **_):
            return {
                "display_allowed": False,
                "frames": [item[0] for item in samples],
                "source_seconds": [item[1] for item in samples],
                "snapshot": {
                    "hand_trusted": False,
                    "own_hand": [],
                    "gold_trusted": False,
                    "gold_tile": None,
                },
                "hint": {"phase": None, "best_discards": [], "issues": ["blocked"]},
            }

        observation = PublicStateObservation(
            top_right_score=1000,
            bottom_left_score=1000,
            hand_number=1,
            remaining_tiles=80,
            score_votes=2,
            hand_votes=2,
            remaining_votes=2,
            issues=(),
        )
        public_reader = SimpleNamespace()
        public_reader.read_window = unittest.mock.Mock(
            return_value=SimpleNamespace(observation=observation)
        )
        meta = {
            "path": "match.mp4",
            "width": 960,
            "height": 448,
            "fps": 30.0,
            "frame_count": 300,
            "duration_seconds": 10.0,
            "aspect_ratio": 960 / 448,
            "reference_frame_size": [2796, 1290],
            "reference_aspect_ratio": 2796 / 1290,
            "aspect_ratio_delta_percent": 1.0,
        }

        with TemporaryDirectory() as tmp:
            video = Path(tmp) / "match.mp4"
            video.write_bytes(b"fixture")
            with (
                patch("workspace.hint_alpha.video_test.probe_video", return_value=meta),
                patch("workspace.hint_alpha.video_test.sha256", return_value="b" * 64),
                patch(
                    "workspace.hint_alpha.video_test.iter_video_samples",
                    return_value=iter(samples),
                ),
                patch(
                    "workspace.hint_alpha.video_test.evaluate_burst",
                    side_effect=runtime_row,
                ),
            ):
                result = run_video_test(
                    video,
                    dataset_root="unused",
                    public_reader=public_reader,
                )

        self.assertEqual(REPLAY_OCR_INTERVAL_SECONDS, 2.0)
        self.assertEqual(public_reader.read_window.call_count, 1)
        self.assertEqual(result["public_state"]["sampled_windows"], 1)
        self.assertGreater(result["public_state"]["reused_windows"], 0)


class DirectVideoRunnerTests(unittest.TestCase):
    def test_runtime_continues_when_public_ocr_errors(self):
        samples = [
            (1, 0.0, object()),
            (2, 0.2, object()),
            (3, 0.4, object()),
            (4, 0.6, object()),
        ]

        def runtime_row(samples, **_):
            ids = [item[0] for item in samples]
            seconds = [item[1] for item in samples]
            return {
                "display_allowed": True,
                "frames": ids,
                "source_seconds": seconds,
                "snapshot": {
                    "hand_trusted": True,
                    "own_hand": ["M1"] * 16,
                    "gold_trusted": True,
                    "gold_tile": "M6",
                },
                "hint": {"phase": "PRE_DRAW", "best_discards": [], "issues": []},
            }

        public_reader = SimpleNamespace()
        public_reader.read_window = unittest.mock.Mock(
            side_effect=[
                RuntimeError("ocr failed"),
                SimpleNamespace(
                    observation=PublicStateObservation(
                        top_right_score=1000,
                        bottom_left_score=1000,
                        hand_number=1,
                        remaining_tiles=80,
                        score_votes=2,
                        hand_votes=2,
                        remaining_votes=2,
                        issues=(),
                    )
                ),
            ]
        )

        meta = {
            "path": "match.mp4",
            "width": 2796,
            "height": 1290,
            "fps": 60.0,
            "frame_count": 600,
            "duration_seconds": 10.0,
            "aspect_ratio": 2796 / 1290,
            "reference_frame_size": [2796, 1290],
            "reference_aspect_ratio": 2796 / 1290,
            "aspect_ratio_delta_percent": 0.0,
        }

        with TemporaryDirectory() as tmp:
            video = Path(tmp) / "match.mp4"
            video.write_bytes(b"fixture")
            report = Path(tmp) / "result.json"
            with (
                patch("workspace.hint_alpha.video_test.probe_video", return_value=meta),
                patch("workspace.hint_alpha.video_test.sha256", return_value="a" * 64),
                patch(
                    "workspace.hint_alpha.video_test.iter_video_samples",
                    return_value=iter(samples),
                ),
                patch(
                    "workspace.hint_alpha.video_test.evaluate_burst",
                    side_effect=runtime_row,
                ),
            ):
                result = run_video_test(
                    video,
                    dataset_root="unused",
                    output_path=report,
                    public_reader=public_reader,
                )

            self.assertEqual(result["runtime"]["windows"], 2)
            self.assertEqual(result["runtime"]["accepted_windows"], 2)
            self.assertEqual(result["public_state"]["error_windows"], 1)
            self.assertEqual(result["public_state"]["hand_number_votes"], {"1": 1})
            self.assertTrue(report.exists())
            self.assertTrue(report.with_suffix(".timeline.json").exists())
            self.assertTrue(report.with_suffix(".timeline.txt").exists())
            saved = json.loads(report.read_text(encoding="utf-8"))
            self.assertFalse(saved["formal_promotion_evidence"])
            self.assertFalse(saved["safe_for_executor"])
            self.assertEqual(saved["timeline"]["status"], "PARTIAL")


if __name__ == "__main__":
    unittest.main()
