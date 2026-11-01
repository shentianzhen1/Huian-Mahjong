import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHAIN = ROOT / "references/vision/2026-10-02/issue69_hand1_m9_draw_s4_discard_s5_chi_s456_chain_v0_1.json"
QUEUE = ROOT / "references/vision/2026-10-01/opponent_public_meld_review_queue_v0_1.json"


class Issue69Hand1CrossActorChiChainTests(unittest.TestCase):
    def test_chain_is_ordered_and_fail_closed(self):
        data = json.loads(CHAIN.read_text(encoding="utf-8"))
        self.assertTrue(data["development_only"])
        seq = data["machine_safe_sequence"]
        anchors = [
            row.get("frame", row.get("approx_frame", row.get("frame_window", [None])[0]))
            for row in seq
        ]
        self.assertEqual(anchors, sorted(anchors))
        machine = data["machine_interpretation"]
        self.assertTrue(machine["cross_actor_order_observed"])
        self.assertTrue(machine["chi_animation_observed"])
        self.assertTrue(machine["opponent_new_meld_observed"])
        self.assertEqual(machine["player_claimed_discard_identity"], "UNKNOWN")
        self.assertFalse(machine["opponent_meld_identity_runtime_confirmed"])
        self.assertFalse(machine["action_machine_confirmed"])
        self.assertFalse(data["formal_promotion_evidence"])
        self.assertFalse(data["safe_for_runtime"])
        self.assertFalse(data["safe_for_executor"])

    def test_s456_reference_matches_existing_review_queue(self):
        data = json.loads(CHAIN.read_text(encoding="utf-8"))
        queue = json.loads(QUEUE.read_text(encoding="utf-8"))
        expected = data["existing_meld_evidence"]
        rows = queue.get("items", queue.get("reviews", queue.get("groups", [])))
        match = next(
            row for row in rows
            if row.get("review_id") == expected["review_id"]
        )
        truth = match.get("reviewed_truth", match.get("truth", {}))
        tiles = truth.get("tiles", match.get("expected_tiles"))
        incoming = truth.get("incoming_tile", match.get("incoming_tile"))
        self.assertEqual(list(tiles), expected["truth_tiles"])
        self.assertEqual(incoming, expected["incoming_tile"])

    def test_claimed_discard_is_not_misrepresented_as_river_growth(self):
        data = json.loads(CHAIN.read_text(encoding="utf-8"))
        self.assertEqual(
            data["machine_interpretation"]["player_claimed_discard_identity"],
            "UNKNOWN",
        )
        self.assertIn(
            "not treated as a long-lived river-growth observation",
            data["caveats"][0],
        )


if __name__ == "__main__":
    unittest.main()
