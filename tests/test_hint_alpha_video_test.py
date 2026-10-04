import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from workspace.hint_alpha.video_test import (automatic_sample_interval, run_video_test, summarize_video_test)
from workspace.vision.tiles_v0_1.public_state import PublicStateObservation





class AutomaticVideoParameterTests(unittest.TestCase):
    def test_short_match_uses_point_two_seconds(self):
        meta = {"fps": 60.0, "duration_seconds": 600.0}
        self.assertAlmostEqual(automatic_sample_interval(meta), 0.2, places=6)

    def test_longer_match_stays_inside_temporal_window(self):
        medium = {"fps": 30.0, "duration_seconds": 1200.0}
        long = {"fps": 60.0, "duration_seconds": 2400.0}
        self.assertLessEqual(automatic_sample_interval(medium) * 2, 0.8)
        self.assertLessEqual(automatic_sample_interval(long) * 2, 0.8)
        self.assertAlmostEqual(automatic_sample_interval(medium), 0.2666666667, places=6)
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
            saved = json.loads(report.read_text(encoding="utf-8"))
            self.assertFalse(saved["formal_promotion_evidence"])
            self.assertFalse(saved["safe_for_executor"])


if __name__ == "__main__":
    unittest.main()
