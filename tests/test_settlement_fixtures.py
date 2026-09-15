import json
import unittest
from pathlib import Path

from huian import HuianRules, YoujinStage


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "settlement_7bc12fa.json"


class SettlementFixtureTests(unittest.TestCase):
    def test_triple_you_608_fixture_matches_rules_terms(self):
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(data["winner_fan"], data["fan_breakdown"]["gold"] + data["fan_breakdown"]["flowers"])
        self.assertEqual(
            (data["current_dealer_base"] + data["winner_fan"]) * data["youjin_multiplier"],
            data["net"],
        )
        terms = HuianRules().youjin_score_terms(
            YoujinStage(data["stage"]),
            winner=data["winner"],
            dealer=data["dealer"],
            winner_fan=data["winner_fan"],
        )
        self.assertEqual(terms.youjin_multiplier, data["youjin_multiplier"])
        self.assertEqual(terms.dealer_multiplier, data["dealer_multiplier"])
        self.assertEqual(
            terms.total_for_current_dealer_base(data["current_dealer_base"]),
            data["net"],
        )


if __name__ == "__main__":
    unittest.main()
