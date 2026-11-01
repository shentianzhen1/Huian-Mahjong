import copy
import json
from pathlib import Path
import unittest

from workspace.vision.issue69_pass_draw_discard_window import (
    review_pass_draw_discard_window,
)

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "references/vision/2026-10-02/issue69_hand1_pass_draw_s9_window_v0_1.json"


class Issue69PassDrawDiscardWindowTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(ART.read_text(encoding="utf-8"))

    def test_exact_source_window_locks_event_order_without_identity_overclaim(self):
        out = review_pass_draw_discard_window(self.data)
        self.assertEqual(out["status"], "SOURCE_LOCKED_EVENT_ORDER")
        self.assertTrue(out["response_resolution_observed"])
        self.assertTrue(out["draw_event_observed"])
        self.assertTrue(out["discard_event_observed"])
        self.assertFalse(out["pass_action_machine_confirmed"])
        self.assertIsNone(out["draw_tile_identity"])
        self.assertIsNone(out["discard_tile_identity"])
        self.assertFalse(out["same_draw_then_discard_identity_machine_confirmed"])
        self.assertFalse(out["safe_for_runtime"])
        self.assertFalse(out["safe_for_executor"])

    def test_reordered_frames_fail_closed(self):
        data = copy.deepcopy(self.data)
        data["event_window"]["draw_region_visible"]["frame"] = 4020
        out = review_pass_draw_discard_window(data)
        self.assertEqual(out["status"], "UNKNOWN")
        self.assertEqual(out["reason"], "frame_order_invalid")

    def test_ui_clear_never_becomes_machine_pass(self):
        data = copy.deepcopy(self.data)
        data["machine_interpretation"]["pass_action_machine_confirmed"] = True
        out = review_pass_draw_discard_window(data)
        self.assertEqual(out["status"], "UNKNOWN")
        self.assertEqual(out["reason"], "machine_semantic_boundary_changed")

    def test_human_truth_cannot_promote_tile_identity(self):
        data = copy.deepcopy(self.data)
        data["machine_interpretation"]["draw_tile_identity"] = "S9"
        out = review_pass_draw_discard_window(data)
        self.assertEqual(out["status"], "UNKNOWN")
        self.assertEqual(out["reason"], "machine_semantic_boundary_changed")

    def test_wrong_source_fails_closed(self):
        data = copy.deepcopy(self.data)
        data["source"]["sha256"] = "0" * 64
        out = review_pass_draw_discard_window(data)
        self.assertEqual(out["status"], "UNKNOWN")
        self.assertEqual(out["reason"], "source_scope_mismatch")


if __name__ == "__main__":
    unittest.main()
