import hashlib
import json
from pathlib import Path
import unittest

from huian import HuianRules
from huian.rules.observed_settlement import HuianObservedSettlementPlugin


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/settlement_b3892b34.json"


class B3892b34EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_one_gold_three_suits_and_two_chi_can_self_draw(self):
        data = self.data
        hand = data["winner_hand_after_draw"]
        melds = data["winner_melds"]
        tiles = hand + [tile for meld in melds for tile in meld["tiles"]]
        self.assertEqual(len(tiles), 17)
        self.assertEqual({tile[0] for tile in tiles}, {"M", "P", "S"})
        rules = HuianRules()
        rules.validate_tiles(tiles)
        result = rules.analyze_hu(
            hand, data["gold_tile"], open_melds=len(melds),
            winning_tile=data["winning_tile"], win_type="zimo")
        self.assertTrue(result.legal)
        self.assertTrue(any(split.gold_used == 1 and split.pair == ("M5", "M5")
                            for split in result.decompositions))
        # A negative counterfactual locks the already-confirmed checked-room gate;
        # this video itself shows self-draw, not an attempted discard Hu.
        self.assertFalse(rules.analyze_hu(
            hand, data["gold_tile"], open_melds=len(melds),
            winning_tile=data["winning_tile"], win_type="pinghu").legal)

    def test_dealer_zimo_68_without_extra_dealer_factor_or_loser_fan(self):
        data = self.data
        self.assertEqual(data["winner"], data["dealer"])
        self.assertEqual(sum(data["fan_breakdown"].values()), data["winner_fan"])
        self.assertEqual(data["winner_fan"], 4)
        self.assertEqual(data["loser_fan_displayed"], 4)
        outcome = HuianObservedSettlementPlugin().settle(
            winner=data["winner"], current_dealer_base=data["current_dealer_base"],
            winner_fan=data["winner_fan"], win_type=data["win_type"])
        self.assertEqual(outcome.rewards, tuple(data["rewards"]))
        self.assertEqual(outcome.rewards, (68, -68))
        self.assertEqual(outcome.multiplier, data["hu_multiplier"])
        self.assertEqual(sum(outcome.rewards), 0)

    def test_fixture_is_bound_to_the_archived_settlement_frame(self):
        data = self.data
        manifest_path = ROOT / data["source_manifest"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["source_sha256"], data["source_sha256"])
        frame = next(item for item in manifest["selected_frames"]
                     if item["file"] == data["settlement_frame"])
        self.assertEqual(frame["time_ms"], data["settlement_time_ms"])
        actual = hashlib.sha256((manifest_path.parent / frame["file"]).read_bytes()).hexdigest()
        self.assertEqual(actual, frame["sha256"])


if __name__ == "__main__":
    unittest.main()
