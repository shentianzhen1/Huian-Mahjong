"""Synthetic scoring tests. Never treat these fixtures as real-video results."""
import unittest

from workspace.vision.original_replay_metrics import score_replay


def fixture():
    return {
        "video_id": "SYNTHETIC_DO_NOT_REPORT_AS_REAL",
        "fps": 30, "duration_frames": 1800,
        "ground_truth": [
            {"frame": 100, "kind": "CHI", "actor": "SELF"},
            {"frame": 300, "kind": "PENG", "actor": "OPPONENT"},
            {"frame": 500, "kind": "KONG", "actor": "SELF"},
        ],
        "predictions": [
            {"frame": 104, "kind": "CHI", "actor": "SELF"},
            {"frame": 299, "kind": "PENG", "actor": "SELF"},
            {"frame": 900, "kind": "CHI", "actor": "OPPONENT"},
            {"frame": 500, "kind": "UNKNOWN", "actor": "UNKNOWN"},
        ],
    }


class ReplayMetricsTests(unittest.TestCase):
    def test_detection_and_reconstruction_separate(self):
        result = score_replay(fixture(), frame_tolerance=15)
        self.assertEqual(result["meld_detection"]["tp"], 2)
        self.assertEqual(result["meld_detection"]["fp"], 1)
        self.assertEqual(result["meld_detection"]["fn"], 1)
        self.assertEqual(result["action_kind_actor_reconstruction"]["tp"], 1)
        self.assertEqual(result["action_kind_actor_reconstruction"]["fp"], 2)
        self.assertEqual(result["action_kind_actor_reconstruction"]["fn"], 2)
        self.assertEqual(result["abstained_predictions"], 1)
        self.assertIsNone(result["complete_action_reconstruction"])
        self.assertFalse(result["formal_source_disjoint_claim"])

    def test_one_prediction_cannot_cover_two_truth_events(self):
        data = fixture()
        data["ground_truth"] = [
            {"frame": 100, "kind": "CHI", "actor": "SELF"},
            {"frame": 101, "kind": "CHI", "actor": "SELF"},
        ]
        data["predictions"] = [
            {"frame": 100, "kind": "CHI", "actor": "SELF"}]
        result = score_replay(data)
        self.assertEqual(result["meld_detection"]["tp"], 1)
        self.assertEqual(result["meld_detection"]["fn"], 1)

    def test_maximum_matching_reassigns_nearest_to_recover_two_events(self):
        # Greedy nearest pairs frame 10 with prediction 8, leaving frame 0
        # unmatched; maximum matching uses (0,8) and (10,16).
        data = fixture()
        data["ground_truth"] = [
            {"frame": 0, "kind": "CHI", "actor": "SELF"},
            {"frame": 10, "kind": "CHI", "actor": "SELF"},
        ]
        data["predictions"] = [
            {"frame": 8, "kind": "CHI", "actor": "SELF"},
            {"frame": 16, "kind": "CHI", "actor": "SELF"},
        ]
        result = score_replay(data, frame_tolerance=8)
        for key in ("meld_detection", "action_kind_actor_reconstruction"):
            self.assertEqual(result[key]["tp"], 2)
            self.assertEqual(result[key]["fp"], 0)
            self.assertEqual(result[key]["fn"], 0)
        self.assertEqual(result["by_kind"]["CHI"]["tp"], 2)
        self.assertIsNone(result["complete_action_reconstruction"])

    def test_actor_mismatch_cannot_be_rescued_by_time_matching(self):
        data = fixture()
        data["ground_truth"] = [
            {"frame": 0, "kind": "CHI", "actor": "SELF"}]
        data["predictions"] = [
            {"frame": 0, "kind": "CHI", "actor": "OPPONENT"}]
        result = score_replay(data, frame_tolerance=0)
        self.assertEqual(result["meld_detection"]["tp"], 1)
        self.assertEqual(result["action_kind_actor_reconstruction"]["tp"], 0)

    def test_empty_predictions_do_not_invent_accuracy(self):
        data = fixture()
        data["predictions"] = []
        result = score_replay(data)
        self.assertIsNone(result["meld_detection"]["precision"])
        self.assertEqual(result["meld_detection"]["recall"], 0)
        self.assertEqual(result["meld_detection"]["fn"], 3)

    def test_missing_ground_truth_cannot_report_recall(self):
        data = fixture()
        data["ground_truth"] = []
        result = score_replay(data)
        self.assertIsNone(result["meld_detection"]["recall"])

    def test_reject_nonfinite_or_boolean_fps(self):
        for bad_fps in (float("nan"), float("inf"), float("-inf"), True, 0, -30):
            with self.subTest(fps=bad_fps):
                data = fixture()
                data["fps"] = bad_fps
                with self.assertRaisesRegex(ValueError, "invalid_duration"):
                    score_replay(data)

    def test_reject_invalid_truth_and_time(self):
        data = fixture()
        data["ground_truth"][0]["actor"] = "UNKNOWN"
        with self.assertRaises(ValueError):
            score_replay(data)
        with self.assertRaises(ValueError):
            score_replay(fixture(), frame_tolerance=-1)


if __name__ == "__main__":
    unittest.main()
