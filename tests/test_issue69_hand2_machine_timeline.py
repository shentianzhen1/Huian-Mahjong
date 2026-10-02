import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "references/vision/2026-10-02/issue69_hand2_machine_timeline_v0_1.json"

class Issue69Hand2TimelineTests(unittest.TestCase):
    def test_post_opening_start_and_action_boundaries_stay_fail_closed(self):
        data=json.loads(P.read_text(encoding="utf-8"))
        self.assertEqual(data["source"]["boundary_status"], "HAND_START_POST_OPENING_ANIMATION")
        self.assertEqual([e["order"] for e in data["events"]], [1,2,3])
        actions=data["events"][1]
        self.assertEqual(actions["observed_actions"], ["PENG","PENG","CHI","CHI"])
        self.assertFalse(actions["tile_identities_confirmed"])
        self.assertTrue(all(x["selected_action"]=="UNKNOWN" for x in actions["response_windows"]))
        self.assertEqual(data["machine_closed_event_count"], 0)
        self.assertFalse(data["formal_promotion_evidence"])
        self.assertFalse(data["safe_for_runtime"])
        self.assertFalse(data["safe_for_hint"])
        self.assertFalse(data["safe_for_executor"])

if __name__ == "__main__":
    unittest.main()
