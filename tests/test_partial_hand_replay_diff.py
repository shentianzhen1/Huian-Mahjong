"""Partial review must not turn approximate human notes into accuracy claims."""
import unittest

from workspace.vision.partial_hand_replay_diff import compare_partial_hand


SHA = "a" * 64


def replay(actions):
    return {"source_sha256": SHA, "time_seconds": [0, 180], "machine_predictions": {
        "source_sha256": SHA, "actions": [
            {"evidence_grade": "DIRECT", "confidence": .8,
             "evidence_refs": ["synthetic:frame"], **action}
            for action in actions
        ],
    }}


class PartialHandReplayDiffTests(unittest.TestCase):
    def test_two_same_tile_discards_remain_distinct_review_rows(self):
        truth = {"source": "hand.mp4", "events": [
            {"approx_second": 87, "actor": "opponent", "type": "DISCARD", "tile_or_meld": "8W"},
            {"approx_second": 91, "actor": "opponent", "type": "DISCARD", "tile_or_meld": "8W"},
        ]}
        actions = [
            {"timestamp_seconds": 87.3, "kind": "DISCARD", "actor": "opponent"},
            {"timestamp_seconds": 91.1, "kind": "DISCARD", "actor": "opponent"},
        ]
        result = compare_partial_hand(truth, replay(actions),
                                      video_name="hand.mp4", video_sha256=SHA)
        self.assertEqual([row["prediction_index"] for row in result["rows"]], [0, 1])
        self.assertEqual([row["human_tile"] for row in result["rows"]], ["8W", "8W"])
        self.assertIsNone(result["accuracy_metrics"])

    def test_claimed_action_and_initial_river_are_outside_river_scope(self):
        truth = {"source": "hand.mp4", "status": "PARTIAL_VERIFIED", "events": [
            {"approx_second": 0, "actor": "tz", "type": "DISCARD_VISIBLE_AT_RECORDING_START",
             "tile_or_meld": "WHITE"},
            {"approx_second": 47, "actor": "opponent", "type": "PLAY_TO_ACTION_AREA",
             "tile_or_meld": "6P"},
            {"approx_second": 49.5, "actor": "tz", "type": "DAIMINKAN",
             "tile_or_meld": "6P"},
            {"approx_second": 101, "actor": "tz", "type": "DISCARD",
             "tile_or_meld": "6W"},
        ]}
        result = compare_partial_hand(truth, replay([{
            "timestamp_seconds": 101.2, "kind": "DISCARD", "actor": "player",
            "tile": None, "evidence_grade": "UNKNOWN",
        }]), video_name="hand.mp4", video_sha256=SHA)
        self.assertEqual([r["status"] for r in result["rows"]], [
            "outside_river_replay_scope", "outside_river_replay_scope",
            "outside_river_replay_scope", "abstained_prediction_nearby",
        ])
        self.assertIsNone(result["accuracy_metrics"])
        self.assertIsNone(result["rows"][3]["machine_tile"])

    def test_source_mismatch_and_unpaired_predictions_are_not_scored(self):
        truth = {"source": "hand.mp4", "events": [{
            "approx_second": 10, "actor": "opponent", "type": "DISCARD",
            "tile_or_meld": "NORTH",
        }]}
        actions = [
            {"timestamp_seconds": 10.4, "kind": "DISCARD", "actor": "player"},
            {"timestamp_seconds": 40, "kind": "DISCARD", "actor": "opponent"},
        ]
        result = compare_partial_hand(truth, replay(actions),
                                      video_name="hand.mp4", video_sha256=SHA)
        self.assertEqual(result["rows"][0]["status"], "candidate_conflict_review_needed")
        self.assertEqual(result["unpaired_machine_prediction_indexes"], [1])
        self.assertIsNone(result["accuracy_metrics"])
        with self.assertRaisesRegex(ValueError, "source filename"):
            compare_partial_hand(truth, replay(actions),
                                 video_name="other.mp4", video_sha256=SHA)
        with self.assertRaisesRegex(ValueError, "SHA256"):
            compare_partial_hand(truth, replay(actions),
                                 video_name="hand.mp4", video_sha256="b" * 64)

    def test_short_replay_excludes_unobserved_truth_periods(self):
        truth = {"source": "hand.mp4", "events": [
            {"approx_second": 10, "actor": "tz", "type": "DISCARD", "tile_or_meld": "NORTH"},
            {"approx_second": 87, "actor": "opponent", "type": "DISCARD", "tile_or_meld": "8W"},
            {"approx_second": 91, "actor": "opponent", "type": "DISCARD", "tile_or_meld": "8W"},
            {"approx_second": 150, "actor": "opponent", "type": "DISCARD", "tile_or_meld": "EAST"},
        ]}
        fragment = replay([])
        fragment["time_seconds"] = [86.003, 92.996]
        result = compare_partial_hand(truth, fragment,
                                      video_name="hand.mp4", video_sha256=SHA)
        self.assertEqual([row["status"] for row in result["rows"]], [
            "outside_replay_window", "no_nearby_prediction_review_needed",
            "no_nearby_prediction_review_needed", "outside_replay_window",
        ])
        self.assertIsNone(result["accuracy_metrics"])
        del fragment["time_seconds"]
        with self.assertRaisesRegex(ValueError, "bounded decoded time window"):
            compare_partial_hand(truth, fragment,
                                 video_name="hand.mp4", video_sha256=SHA)

    def test_same_actor_alignment_precedes_nearest_opposite_actor(self):
        truth = {"source": "hand.mp4", "events": [
            {"approx_second": 87, "actor": "opponent", "type": "DISCARD", "tile_or_meld": "8W"},
            {"approx_second": 89, "actor": "tz", "type": "DISCARD", "tile_or_meld": "NORTH"},
        ]}
        result = compare_partial_hand(truth, replay([{
            "timestamp_seconds": 87.995, "kind": "DISCARD", "actor": "player",
            "evidence_grade": "UNKNOWN",
        }]), video_name="hand.mp4", video_sha256=SHA)
        self.assertEqual(result["rows"][0]["status"], "no_nearby_prediction_review_needed")
        self.assertEqual(result["rows"][1]["status"], "abstained_prediction_nearby")
        self.assertEqual(result["rows"][1]["prediction_index"], 0)

    def test_latest_human_record_undated_and_rejected_events_are_not_scored(self):
        truth = {"source": "hand.mp4", "events": [
            {"approx_second": None, "actor": "tz", "type": "DISCARD", "tile_or_meld": "2S"},
            {"approx_second": 123, "actor": "tz", "type": "DISCARD", "tile_or_meld": "1S",
             "verification_status": "REJECTED_USER_CONFIRMED_NO_1S_DISCARD"},
            {"approx_second": 89, "actor": "tz", "type": "DISCARD", "tile_or_meld": "NORTH"},
        ]}
        fragment = replay([])
        fragment["time_seconds"] = [86, 93]
        result = compare_partial_hand(truth, fragment,
                                      video_name="hand.mp4", video_sha256=SHA)
        self.assertEqual([row["status"] for row in result["rows"]], [
            "no_time_anchor_review_needed", "rejected_human_event_excluded",
            "no_nearby_prediction_review_needed",
        ])
        self.assertIsNone(result["accuracy_metrics"])


if __name__ == "__main__":
    unittest.main()
