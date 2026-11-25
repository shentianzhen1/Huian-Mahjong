import copy
import json
from pathlib import Path
import unittest

from workspace.vision.issue69_claimed_discard_display import (
    review_claimed_discard_display,
)

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "references/vision/2026-10-02/issue69_hand1_claimed_discard_p6_display_v0_1.json"


class Issue69ClaimedDiscardDisplayTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(ART.read_text(encoding="utf-8"))

    def test_real_six_frame_display_is_p6_development_evidence(self):
        out = review_claimed_discard_display(self.data)
        self.assertEqual(out["status"], "DIRECT_DISPLAY_P6_DEVELOPMENT")
        self.assertEqual(out["tile_candidate"], "P6")
        self.assertEqual(out["valid_frame_votes"], 6)
        self.assertTrue(out["claimed_discard_display_directly_observed"])
        self.assertFalse(out["river_growth_directly_observed"])
        self.assertFalse(out["action_kind_inferred"])
        self.assertFalse(out["machine_confirmed"])
        self.assertFalse(out["runtime_eligible"])
        self.assertFalse(out["safe_for_runtime"])
        self.assertFalse(out["safe_for_executor"])

    def test_wrong_source_fails_closed(self):
        data = copy.deepcopy(self.data)
        data["source"]["sha256"] = "0" * 64
        out = review_claimed_discard_display(data)
        self.assertEqual(out["status"], "UNKNOWN")
        self.assertEqual(out["reason"], "source_scope_mismatch")

    def test_five_pips_fail_closed(self):
        data = copy.deepcopy(self.data)
        data["observations"][0]["circles"] = data["observations"][0]["circles"][:5]
        out = review_claimed_discard_display(data)
        self.assertEqual(out["status"], "UNKNOWN")
        self.assertEqual(out["reason"], "circle_count_not_six")

    def test_wrong_colour_layout_fails_closed(self):
        data = copy.deepcopy(self.data)
        data["observations"][0]["circles"][0][3] = 3.0
        out = review_claimed_discard_display(data)
        self.assertEqual(out["status"], "UNKNOWN")
        self.assertEqual(out["reason"], "top_pair_not_green")

    def test_region_never_infers_action_kind(self):
        data = copy.deepcopy(self.data)
        data["semantic_boundary"]["action_kind_inferred_from_this_region"] = True
        out = review_claimed_discard_display(data)
        self.assertEqual(out["status"], "UNKNOWN")
        self.assertEqual(out["reason"], "semantic_boundary_changed")


if __name__ == "__main__":
    unittest.main()
