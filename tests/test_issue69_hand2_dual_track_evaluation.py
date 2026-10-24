import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "references/vision/2026-10-02/issue69_hand2_dual_track_evaluation_v0_1.json"

class Issue69Hand2DualTrackEvaluationTests(unittest.TestCase):
    def test_blind_river_replay_stays_fail_closed_and_private_slot_layout_stays_local(self):
        data = json.loads(P.read_text(encoding="utf-8"))
        machine = data["tracks"]["machine"]
        replay = machine["river_replay_blind_run"]
        dense = machine["dense_river_supplement"]

        self.assertEqual(machine["status"], "RIVER_REPLAY_EXECUTED_FULL_IDENTITY_STACK_PENDING")
        self.assertFalse(replay["truth_loaded_before_prediction"])
        self.assertEqual(replay["frames_decoded"], 2400)
        self.assertEqual(replay["counts"]["assembled_actions"], 7)
        self.assertEqual(replay["counts"]["unknown_graded_actions"], 7)
        self.assertEqual(replay["counts"]["known_tile_actions"], 0)
        self.assertIsNone(replay["development_evaluation"])

        self.assertEqual(dense["status"], "LOCAL_DEVELOPMENT_DIAGNOSTIC_EXECUTED")
        self.assertFalse(dense["private_slot_layout_committed"])
        self.assertFalse(dense["raw_observation_emitted"])
        self.assertFalse(dense["action_kind_emitted"])
        self.assertFalse(dense["tile_identity_emitted"])
        self.assertGreater(dense["opponent_record_prefix_growth_candidates"], 0)
        self.assertGreater(dense["player_record_prefix_growth_candidates"], 0)

        serialized = json.dumps(data, sort_keys=True)
        self.assertNotIn('"slots"', serialized)
        self.assertNotIn('"bbox"', serialized)
        self.assertFalse(data["formal_promotion_evidence"])
        self.assertFalse(data["safe_for_runtime"])
        self.assertFalse(data["safe_for_hint"])
        self.assertFalse(data["safe_for_executor"])

if __name__ == "__main__":
    unittest.main()
