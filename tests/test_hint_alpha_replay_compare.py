from copy import deepcopy
import unittest

from workspace.hint_alpha.replay_compare import check_reviewed_endpoints, compare_video_reports


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
        before["rows"][0]["diagnostics"] = {"primary_advice_blocker": "geometry"}
        after["rows"][3]["diagnostics"] = {"primary_advice_blocker": "stability"}
        before["rows"][1]["snapshot"] = {"own_hand": ["M1"], "gold_tile": "P1"}
        after["rows"][2]["snapshot"] = {"own_hand": ["P1"], "gold_tile": "M1"}
        result = compare_video_reports(before, after)
        self.assertEqual(result["advice_gained_from_blockers"], {"geometry": 1})
        self.assertEqual(result["advice_lost_to_blockers"], {"stability": 1})
        self.assertEqual(result["shared_endpoints"], 3)
        self.assertEqual(result["candidate_only_discards"], 1)
        self.assertEqual(result["changed_frames"], {
            12: ["advice_gained", "discard_gained"],
            24: ["concealed_hand_changed", "gold_changed", "discard_set_changed"],
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

    def test_reviewed_endpoint_checks_pixels_inputs_and_advice(self):
        candidate = report((12, "P4"), (24, None), (36, "P4"))
        candidate["rows"][0]["snapshot"] = {
            "own_hand": ["M2", "M1"], "gold_tile": "M4", "melds": [[], []],
        }
        expected = {"hand": ["M1", "M2"], "gold": "M4", "own_meld_count": 0,
                    "phase": "POST_DRAW", "shanten": 1, "discards": ["P4"]}
        evidence = {"sources": [{"source_sha256": "video", "frames": [
            {**expected, "frame": 12, "pixel_sha256": "pixel-12"},
            {**expected, "frame": 24, "pixel_sha256": "pixel-24"},
            {**expected, "frame": 36, "pixel_sha256": "different"},
            {**expected, "frame": 48, "pixel_sha256": "pixel-48"},
        ]}]}
        result = check_reviewed_endpoints(candidate, evidence)
        self.assertEqual(result["matching_endpoints"], 1)
        self.assertEqual(result["issues_by_frame"], {
            24: ["advice_blocked"], 36: ["endpoint_pixel_mismatch"], 48: ["endpoint_missing"],
        })
        candidate["rows"][0]["snapshot"]["gold_tile"] = "M5"
        candidate["rows"][0]["hint"]["best_discards"] = [{"discard": "M2"}]
        result = check_reviewed_endpoints(candidate, evidence)
        self.assertEqual(result["issues_by_frame"][12], ["gold", "discards"])
