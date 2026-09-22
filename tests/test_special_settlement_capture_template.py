from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (
    ROOT
    / "references"
    / "rules"
    / "2026-09-22"
    / "special_settlement_capture_template.json"
)


class SpecialSettlementCaptureTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(TEMPLATE.read_text(encoding="utf-8"))

    def test_template_starts_unknown_and_targets_open_p0_evidence(self):
        self.assertEqual(
            self.data["schema_version"],
            "special_settlement_capture_v0_1",
        )
        self.assertEqual(self.data["evidence_level"], "unknown")
        self.assertIsNone(self.data["issue_number"])

    def test_source_identity_and_full_timeline_fields_exist(self):
        self.assertEqual(
            set(self.data["source"]),
            {"sha256", "session", "file_label"},
        )
        self.assertEqual(
            set(self.data["timestamps"]),
            {"pre_trigger", "prompt", "decision", "settlement", "next_hand"},
        )

    def test_pre_settlement_state_keeps_accounting_and_structure(self):
        required = {
            "dealer",
            "current_dealer_base",
            "scores",
            "gold_tile",
            "playable_gold_count",
            "flowers",
            "concealed_hand",
            "exposed_melds",
            "remaining_tiles",
        }
        self.assertTrue(required.issubset(self.data["state_before"]))

    def test_terminal_fields_can_close_formula_and_dealer_flow(self):
        required = {
            "winner",
            "scores_after",
            "net_transfer",
            "displayed_fan",
            "displayed_multiplier",
            "displayed_lines",
            "next_dealer",
            "next_hand_index",
        }
        self.assertTrue(required.issubset(self.data["settlement"]))

    def test_unknown_values_are_explicit_not_zero_filled(self):
        self.assertIsNone(self.data["settlement"]["displayed_fan"])
        self.assertIsNone(self.data["settlement"]["displayed_multiplier"])
        self.assertIsNone(self.data["settlement"]["net_transfer"])
        self.assertEqual(self.data["unknown_fields"], [])


if __name__ == "__main__":
    unittest.main()
