import unittest

from huian import HuianRules, YoujinStage
from huian.rules.youjin_analysis import (
    analyze_youjin_melds,
    can_youjin_upgrade_after_draw,
    is_youjin_ready_hand,
    youjin_entry_discards,
    youjin_score_terms,
)


READY = [
    "M1", "M2", "P9",
    "M4", "M5", "M6",
    "P1", "P2", "P3",
    "S3", "S4", "P9",
    "E", "E", "E",
    "P9",
]


class YoujinAnalysisBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.rules = HuianRules()

    def test_rules_methods_delegate_to_same_structural_results(self):
        self.assertEqual(
            self.rules.is_youjin_ready_hand(READY, "P9"),
            is_youjin_ready_hand(self.rules, READY, "P9"),
        )
        self.assertEqual(
            self.rules.analyze_youjin_melds(READY, "P9"),
            analyze_youjin_melds(self.rules, READY, "P9"),
        )
        hand = READY + ["M9"]
        self.assertEqual(
            self.rules.youjin_entry_discards(hand, "P9"),
            youjin_entry_discards(self.rules, hand, "P9"),
        )

    def test_helper_paths_preserve_ready_hand_override(self):
        class OverrideRules(HuianRules):
            def __init__(self):
                super().__init__()
                self.calls = 0

            def is_youjin_ready_hand(self, hand, gold_tile, open_melds=0):
                self.calls += 1
                return False

        rules = OverrideRules()
        self.assertFalse(
            analyze_youjin_melds(rules, READY, "P9").legal
        )
        self.assertEqual(rules.calls, 1)

        rules.calls = 0
        self.assertEqual(
            youjin_entry_discards(rules, READY + ["M9"], "P9"),
            (),
        )
        self.assertGreater(rules.calls, 0)

        rules.calls = 0
        self.assertFalse(
            can_youjin_upgrade_after_draw(
                rules,
                [
                    "M1", "M2", "M3",
                    "M4", "M5", "M6",
                    "P1", "P2", "P3",
                    "S1", "S2", "S3",
                    "E", "E", "E",
                    "P9", "P9",
                ],
                "P9",
            )
        )
        self.assertEqual(rules.calls, 1)

    def test_upgrade_and_score_terms_match_helper_boundary(self):
        ready = [
            "M1", "M2", "M3",
            "M4", "M5", "M6",
            "P1", "P2", "P3",
            "S1", "S2", "S3",
            "E", "E", "E",
            "P9",
        ]
        draw = ready + ["P9"]
        self.assertEqual(
            self.rules.can_youjin_upgrade_after_draw(draw, "P9"),
            can_youjin_upgrade_after_draw(self.rules, draw, "P9"),
        )
        self.assertEqual(
            self.rules.youjin_score_terms(
                YoujinStage.DOUBLE_YOU, winner=1, dealer=0, winner_fan=3
            ),
            youjin_score_terms(
                self.rules,
                YoujinStage.DOUBLE_YOU,
                winner=1,
                dealer=0,
                winner_fan=3,
            ),
        )


if __name__ == "__main__":
    unittest.main()
