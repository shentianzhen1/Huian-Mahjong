import hashlib
import json
from pathlib import Path
import unittest

from huian import HuianRules, YoujinStage


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/settlement_66fe863f.json"


class Youjin66fe863fEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_transcribed_shape_and_kong_physical_count_are_consistent(self):
        data = self.data
        before_discard = list(data["winner_hand_before_youjin_discard"])
        before_discard.remove(data["youjin_discard"])
        before_draw = data["winner_hand_before_final_draw"]
        hand = data["winner_hand_after_final_draw"]
        self.assertEqual(before_discard, before_draw)
        self.assertEqual(hand, before_draw + [data["winning_tile"]])
        self.assertEqual(len(before_draw), 10)
        self.assertEqual(len(hand), 11)
        melds = data["winner_melds"]
        exposed_tiles = [tile for meld in melds for tile in meld["tiles"]]
        self.assertEqual(len(exposed_tiles), 7)
        self.assertEqual(len(before_draw + exposed_tiles), 17)
        self.assertEqual(len(hand + exposed_tiles), 18)
        self.assertEqual(exposed_tiles.count("P1"), 4)
        rules = HuianRules()
        rules.validate_tiles(hand + exposed_tiles)

        # This ordinary structural query is NOT a Youjin eligibility check.
        # The replay labels the win YOUJIN; no special transition is executed.
        structural_result = rules.analyze_hu(
            hand, data["gold_tile"], open_melds=len(melds),
            winning_tile=data["winning_tile"], win_type="zimo")
        self.assertTrue(structural_result.legal)
        self.assertTrue(any(
            split.pair == ("M7", "GOLD") and split.gold_used == 1
            for split in structural_result.decompositions))
        self.assertFalse(data["structural_analysis"]["is_client_decomposition"])
        self.assertEqual(data["win_type"], "YOUJIN")

    def test_youjin_net_100_and_display_40_use_distinct_bases(self):
        data = self.data
        self.assertNotEqual(data["winner"], data["dealer"])
        self.assertEqual(sum(data["fan_breakdown"].values()), data["winner_fan"])
        self.assertEqual(data["winner_fan"], 5)
        terms = HuianRules().youjin_score_terms(
            YoujinStage(data["stage"]), winner=data["winner"],
            dealer=data["dealer"], winner_fan=data["winner_fan"])
        self.assertEqual(terms.youjin_multiplier, 4)
        self.assertEqual(terms.dealer_multiplier, data["dealer_multiplier"])
        net = terms.total_for_current_dealer_base(data["current_dealer_base"])
        self.assertEqual(net, 100)
        self.assertEqual(data["rewards"], [net, -net])
        self.assertEqual(sum(data["rewards"]), 0)
        displayed = (
            (data["winner_own_base"] + data["winner_fan"])
            * terms.youjin_multiplier)
        self.assertEqual(displayed, data["winner_displayed_value"])
        self.assertEqual(displayed, 40)
        self.assertNotEqual(displayed, net)
        self.assertEqual(data["loser_fan_displayed"], 1)

    def test_fixture_is_bound_to_the_archived_settlement_frame(self):
        data = self.data
        manifest_path = ROOT / data["source_manifest"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["source_sha256"], data["source_sha256"])
        frame = next(item for item in manifest["selected_frames"]
                     if item["file"] == data["settlement_frame"])
        self.assertEqual(frame["time_ms"], data["settlement_time_ms"])
        actual = hashlib.sha256(
            (manifest_path.parent / frame["file"]).read_bytes()).hexdigest()
        self.assertEqual(actual, frame["sha256"])


if __name__ == "__main__":
    unittest.main()
