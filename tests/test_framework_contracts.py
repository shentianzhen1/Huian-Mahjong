import unittest

from mahjong_framework import MahjongOpeningPlugin, MahjongRulesPlugin
from huian.rules import HuianRulesAdapter
from huian.environment.opening import HuianOpeningPlugin


class FrameworkContractTests(unittest.TestCase):
    def test_huian_rules_adapter_implements_neutral_rules_contract(self):
        adapter = HuianRulesAdapter()
        self.assertIsInstance(adapter, MahjongRulesPlugin)
        self.assertEqual(adapter.variant_id, "huian.two_player.v0_1")

    def test_huian_opening_implements_neutral_opening_contract(self):
        opening = HuianOpeningPlugin()
        self.assertIsInstance(opening, MahjongOpeningPlugin)
        self.assertEqual(opening.variant_id, "huian.two_player.v0_1")


if __name__ == "__main__":
    unittest.main()