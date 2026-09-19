import json
import unittest
from pathlib import Path

from huian import HuianRules, YoujinStage
from workspace.simulator import MatchProgressState


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "settlement_7bc12fa.json"
MATCH_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "settlement_room541913_8hands.json"


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


    def test_room541913_full_match_fixture_replays_scores_and_dealer_bases(self):
        data = json.loads(MATCH_FIXTURE.read_text(encoding="utf-8"))
        state = MatchProgressState.initial(dealer=data["initial_dealer"])
        self.assertEqual(list(state.scores), data["starting_scores"])

        for hand in data["hands"]:
            self.assertEqual(state.hand_index + 1, hand["hand"])
            self.assertEqual(state.dealer, hand["dealer"])
            self.assertEqual(state.consecutive_dealer_hands, hand["dealer_streak"])
            self.assertEqual(state.current_dealer_base, hand["current_dealer_base"])
            self.assertEqual(
                (hand["current_dealer_base"] + hand["winner_fan"])
                * hand["multiplier"],
                hand["net"],
            )
            rewards = tuple(hand["rewards"])
            state = state.apply_settled_hand(rewards, winner=hand["winner"])
            self.assertEqual(list(state.scores), hand["scores_after"])

        self.assertTrue(state.complete)
        self.assertEqual(list(state.scores), data["final_scores"])
        self.assertEqual(sum(state.scores), 2000)

    def test_room541913_hand5_proves_youjin_can_settle_with_two_gold_fan(self):
        data = json.loads(MATCH_FIXTURE.read_text(encoding="utf-8"))
        hand5 = data["hands"][4]
        self.assertEqual(hand5["method"], "YOUJIN")
        self.assertEqual(hand5["multiplier"], 4)
        self.assertEqual(hand5["fan_breakdown"]["gold"], 2)
        self.assertEqual(hand5["net"], 76)
        terms = HuianRules().youjin_score_terms(
            YoujinStage.YOUJIN,
            winner=hand5["winner"],
            dealer=hand5["dealer"],
            winner_fan=hand5["winner_fan"],
        )
        self.assertEqual(terms.dealer_multiplier, 1)
        self.assertEqual(
            terms.total_for_current_dealer_base(hand5["current_dealer_base"]),
            76,
        )



if __name__ == "__main__":
    unittest.main()
