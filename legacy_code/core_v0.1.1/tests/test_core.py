
import unittest
import json
from pathlib import Path

from qzcore.tiles import full_wall
from qzcore.win_checker import can_win
from qzcore.ting import ting_tiles
from qzcore.scoring import two_player_net_score
from qzcore.legal_actions import can_peng, can_ming_gang, can_an_gang, chi_options

class CoreTests(unittest.TestCase):
    def test_wall_144(self):
        self.assertEqual(len(full_wall()), 144)

    def test_normal_win_17(self):
        hand = [
            "M1","M1",
            "M2","M3","M4",
            "M5","M6","M7",
            "P1","P2","P3",
            "S1","S2","S3",
            "E","E","E"
        ]
        self.assertTrue(can_win(hand))

    def test_gold_fills_sequence_for_zimo(self):
        gold = "P9"
        hand = [
            "M1","M1",
            "M2","M3",gold,
            "M5","M6","M7",
            "P1","P2","P3",
            "S1","S2","S3",
            "E","E","E"
        ]
        self.assertTrue(can_win(hand, gold_tile=gold, win_type="zimo"))

    def test_single_gold_cannot_pinghu(self):
        gold = "P9"
        hand = [
            "M1","M1",
            "M2","M3",gold,
            "M5","M6","M7",
            "P1","P2","P3",
            "S1","S2","S3",
            "E","E","E"
        ]
        self.assertFalse(can_win(hand, gold_tile=gold, win_type="pinghu"))

    def test_double_gold_cannot_pinghu(self):
        gold = "P9"
        hand = [
            gold,gold,
            "M1","M2","M3",
            "M4","M5","M6",
            "P1","P2","P3",
            "S1","S2","S3",
            "E","E","E"
        ]
        self.assertTrue(can_win(hand, gold_tile=gold, win_type="zimo"))
        self.assertFalse(can_win(hand, gold_tile=gold, win_type="pinghu"))

    def test_ting_east(self):
        hand = [
            "M1","M1",
            "M2","M3","M4",
            "M5","M6","M7",
            "P1","P2","P3",
            "S1","S2","S3",
            "E","E"
        ]
        waits = [x["tile"] for x in ting_tiles(hand)]
        self.assertIn("E", waits)

    def test_real_two_player_settlement(self):
        self.assertEqual(two_player_net_score(5,24,10,2,win_type="zimo"), 34)

    def test_default_match_rounds_is_8(self):
        cfg = json.loads((Path(__file__).resolve().parents[1] / "rules_config.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["default_match_rounds"], 8)

    def test_actions(self):
        hand = ["M2","M2","M2","M3","M4","M5","M5","M5","M5"]
        self.assertTrue(can_peng(hand,"M2"))
        self.assertTrue(can_ming_gang(hand,"M2"))
        self.assertTrue(can_an_gang(hand,"M5"))
        self.assertIn(("M2","M3","M4"), chi_options(hand,"M3",allow_chi=True))

if __name__ == "__main__":
    unittest.main()
