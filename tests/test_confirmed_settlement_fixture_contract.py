from __future__ import annotations

import json
from pathlib import Path
import unittest


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
INDEX = FIXTURE_DIR / "settlement_index.json"


class ConfirmedSettlementFixtureContractTests(unittest.TestCase):
    """Repository-wide contract for direct CONFIRMED settlement evidence.

    Dedicated evidence tests remain responsible for hand transcription and
    rule-specific semantics. This contract prevents a confirmed settlement
    fixture from becoming orphaned or losing basic accounting guarantees.
    """

    @classmethod
    def setUpClass(cls):
        cls.index = json.loads(INDEX.read_text(encoding="utf-8"))

    def test_index_covers_every_settlement_fixture(self):
        indexed = {item["file"] for item in self.index["fixtures"]}
        actual = {
            path.name
            for path in FIXTURE_DIR.glob("settlement_*.json")
            if path.name != INDEX.name
        }
        self.assertEqual(indexed, actual)

    def test_index_entries_are_confirmed_and_unique(self):
        files = [item["file"] for item in self.index["fixtures"]]
        self.assertEqual(len(files), len(set(files)))
        for item in self.index["fixtures"]:
            with self.subTest(file=item["file"]):
                self.assertEqual(item["evidence_status"], "CONFIRMED")
                self.assertIn(item["kind"], {"single", "match"})
                self.assertTrue((FIXTURE_DIR / item["file"]).is_file())

    def test_single_settlements_preserve_formula_and_zero_sum(self):
        for item in self.index["fixtures"]:
            if item["kind"] != "single":
                continue
            with self.subTest(file=item["file"]):
                data = json.loads(
                    (FIXTURE_DIR / item["file"]).read_text(encoding="utf-8")
                )
                multiplier = data[item["multiplier_field"]]
                expected_net = (
                    data["current_dealer_base"] + data["winner_fan"]
                ) * multiplier

                if "net" in data:
                    self.assertEqual(data["net"], expected_net)

                rewards = data.get("rewards")
                if rewards is not None:
                    self.assertEqual(len(rewards), 2)
                    self.assertEqual(sum(rewards), 0)
                    winner = data["winner"]
                    self.assertEqual(rewards[winner], expected_net)
                    self.assertEqual(rewards[1 - winner], -expected_net)

    def test_full_match_fixtures_preserve_ledger_and_hand_order(self):
        for item in self.index["fixtures"]:
            if item["kind"] != "match":
                continue
            with self.subTest(file=item["file"]):
                data = json.loads(
                    (FIXTURE_DIR / item["file"]).read_text(encoding="utf-8")
                )
                scores = list(data["starting_scores"])
                self.assertEqual(sum(scores), 2000)

                for expected_hand, hand in enumerate(data["hands"], start=1):
                    self.assertEqual(hand["hand"], expected_hand)
                    self.assertEqual(sum(hand["rewards"]), 0)
                    expected_net = (
                        hand["current_dealer_base"] + hand["winner_fan"]
                    ) * hand["multiplier"]
                    self.assertEqual(hand["net"], expected_net)
                    self.assertEqual(
                        hand["rewards"][hand["winner"]],
                        expected_net,
                    )
                    scores = [
                        scores[seat] + hand["rewards"][seat]
                        for seat in (0, 1)
                    ]
                    self.assertEqual(scores, hand["scores_after"])
                    self.assertEqual(sum(scores), 2000)

                self.assertEqual(scores, data["final_scores"])


if __name__ == "__main__":
    unittest.main()
