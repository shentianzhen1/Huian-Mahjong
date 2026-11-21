from copy import deepcopy
import unittest

from workspace.hint_alpha.replay_compare import compare_video_reports


def report(*windows):
    return {
        "source": {"sha256": "video", "start_seconds": 0, "requested_duration_seconds": 10},
        "identity_threshold": 0.82,
        "rows": [
            {
                "frames": [frame],
                "pixel_sha256": [f"pixel-{frame}"],
                "display_allowed": bool(discard),
                "hint": {
                    "shanten": 1 if discard else None,
                    "phase": "POST_DRAW" if discard else None,
                    "best_discards": [{"discard": discard}] if discard else [],
                },
            }
            for frame, discard in windows
        ],
    }


class ReplayCompareTests(unittest.TestCase):
    def test_cadence_only_and_shared_changes_are_counted_separately(self):
        before = report((12, None), (24, "P4"), (36, "M1"))
        after = report((6, "S1"), (12, "P4"), (24, "P5"), (36, None))
        result = compare_video_reports(before, after)
        self.assertEqual(result["shared_endpoints"], 3)
        self.assertEqual(result["candidate_only_discards"], 1)
        self.assertEqual(result["changed_frames"], {
            12: ["advice_gained", "discard_gained"],
            24: ["discard_set_changed"],
            36: ["advice_lost", "discard_lost"],
        })

    def test_changed_pixels_or_interrupted_reports_fail_comparison(self):
        before = report((12, "P4"))
        after = deepcopy(before)
        after["rows"][0]["pixel_sha256"] = ["other"]
        with self.assertRaisesRegex(ValueError, "pixel SHA256 mismatch"):
            compare_video_reports(before, after)
        after = deepcopy(before)
        after["stopped_early"] = True
        with self.assertRaisesRegex(ValueError, "completed replay"):
            compare_video_reports(before, after)
