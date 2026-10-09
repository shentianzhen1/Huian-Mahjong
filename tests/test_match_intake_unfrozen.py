"""10-9 intake must not become a score or a holdout."""
from __future__ import annotations

import unittest
from pathlib import Path

from huian.evidence.match_intake import (
    UnfrozenMatchIntake,
    load_match_intake,
    require_frozen_ledger,
)

INTAKE = Path("references/gameplay/2026-10-09/match_10_9_eight_hand/intake_v0_1.json")


class MatchIntakeUnfrozenTests(unittest.TestCase):
    def test_10_9_intake_is_revealed_and_unfrozen(self):
        payload = load_match_intake(INTAKE)
        self.assertEqual(len(payload["clips"]), 8)
        self.assertEqual(payload["ledger_status"], "UNKNOWN")
        self.assertFalse(payload["independent_holdout"])
        self.assertTrue(payload["revealed_development_only"])
        self.assertTrue(all(clip["settlement"] == "UNKNOWN" for clip in payload["clips"]))
        unhashed = [clip["index"] for clip in payload["clips"] if clip["sha256"] == "HASH_UNKNOWN"]
        self.assertEqual(unhashed, [4, 7])

    def test_unfrozen_ledger_cannot_be_used_as_numbers(self):
        payload = load_match_intake(INTAKE)
        with self.assertRaises(UnfrozenMatchIntake):
            require_frozen_ledger(payload)


if __name__ == "__main__":
    unittest.main()
