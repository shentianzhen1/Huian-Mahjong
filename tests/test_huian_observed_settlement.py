import unittest

from mahjong_framework import MahjongSettlementPlugin
from huian.rules import HuianObservedSettlementPlugin, UnknownRuleError


class ObservedSettlementTests(unittest.TestCase):
    def setUp(self):
        self.plugin = HuianObservedSettlementPlugin()

    def test_plugin_contract_and_direct_capture_examples(self):
        self.assertIsInstance(self.plugin, MahjongSettlementPlugin)
        examples = (
            ("PINGHU", 0, 10, 1, 11),
            ("PINGHU", 1, 15, 1, 16),
            ("ZIMO", 0, 10, 9, 38),
            ("ZIMO", 1, 15, 4, 38),
        )
        for win_type, winner, base, fan, net in examples:
            result = self.plugin.settle(winner=winner, current_dealer_base=base,
                                        winner_fan=fan, win_type=win_type)
            self.assertEqual(result.rewards[winner], net)
            self.assertEqual(sum(result.rewards), 0)
            self.assertEqual(result.win_type, win_type)

    def test_unobserved_special_outcomes_remain_blocked(self):
        for win_type in ("QIANGJIN", "SANJINDAO", "YOUJIN", "LIUJU"):
            with self.assertRaises(UnknownRuleError):
                self.plugin.settle(winner=0, current_dealer_base=10,
                                   winner_fan=1, win_type=win_type)


if __name__ == "__main__":
    unittest.main()