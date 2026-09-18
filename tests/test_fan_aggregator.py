import json
from pathlib import Path
import unittest

from huian import HuianRules
from huian.rules import EvidenceStatus
from huian._legacy import env


ROOT = Path(__file__).resolve().parents[1]


def load_fixture(name):
    return json.loads((ROOT / "tests" / "fixtures" / name).read_text(encoding="utf-8"))


def melds_from_fixture(items):
    result = []
    for item in items:
        kind = item["kind"]
        source = None if kind == "AN_GANG" else 1
        result.append(env.Meld(kind, list(item["tiles"]), source))
    return result


class FanAggregatorTests(unittest.TestCase):
    def setUp(self):
        self.rules = HuianRules()

    def test_b3892b34_reproduces_observed_four_fan(self):
        data = load_fixture("settlement_b3892b34.json")
        result = self.rules.aggregate_fan(
            data["winner_hand_after_draw"],
            melds_from_fixture(data["winner_melds"]),
            env.FLOWERS[:data["winner_flower_count"]],
            data["gold_tile"],
        )
        self.assertTrue(result.complete)
        self.assertEqual(result.fan, data["winner_fan"])
        self.assertEqual(result.fan, 4)
        self.assertEqual(
            sorted((item.category, item.fan) for item in result.components),
            [("concealed_triplet", 1), ("flowers", 2), ("gold", 1)],
        )

    def test_66fe863f_reproduces_observed_five_fan(self):
        data = load_fixture("settlement_66fe863f.json")
        result = self.rules.aggregate_fan(
            data["winner_hand_after_final_draw"],
            melds_from_fixture(data["winner_melds"]),
            env.FLOWERS[:data["winner_flower_count"]],
            data["gold_tile"],
        )
        self.assertTrue(result.complete)
        self.assertEqual(result.fan, data["winner_fan"])
        self.assertEqual(result.fan, 5)
        kong = next(item for item in result.components if item.category == "kong")
        self.assertEqual(kong.fan, 2)
        self.assertEqual(kong.status, EvidenceStatus.CONFIRMED)

    def test_gold_filled_triplet_is_not_natural_triplet_fan(self):
        # Pair M1/M1; four natural sequences; NN+gold is the fifth group.
        hand = [
            "M1", "M1",
            "M2", "M3", "M4",
            "M5", "M6", "M7",
            "P1", "P2", "P3",
            "S1", "S2", "S3",
            "N", "N", "P9",
        ]
        result = self.rules.aggregate_fan(hand, gold_tile="P9")
        self.assertTrue(result.complete)
        self.assertEqual(result.fan, 1)
        self.assertEqual(
            [(item.category, item.fan) for item in result.components],
            [("gold", 1)],
        )

    def test_discard_completed_triplet_is_not_concealed_triplet_fan(self):
        hand = [
            "M1", "M1",
            "M2", "M3", "M4",
            "M5", "M6", "M7",
            "P1", "P2", "P3",
            "S1", "S2", "S3",
            "E", "E", "E",
        ]

        zimo = self.rules.analyze_hu(
            hand, winning_tile="E", win_type="zimo")
        zimo_fan = self.rules.aggregate_fan(
            hand, hu_result=zimo)
        self.assertTrue(zimo_fan.complete)
        self.assertEqual(zimo_fan.fan, 2)
        self.assertEqual(
            [(item.category, item.fan) for item in zimo_fan.components],
            [("concealed_triplet", 2)],
        )

        pinghu = self.rules.analyze_hu(
            hand, winning_tile="E", win_type="pinghu")
        pinghu_fan = self.rules.aggregate_fan(
            hand, hu_result=pinghu)
        self.assertTrue(pinghu_fan.complete)
        self.assertEqual(pinghu_fan.fan, 0)
        self.assertFalse(any(
            item.category == "concealed_triplet"
            for item in pinghu_fan.components
        ))

    def test_two_gold_fan_is_cumulative_one_each(self):
        hand = [
            "P9", "P9",
            "M1", "M2", "M3",
            "M4", "M5", "M6",
            "M7", "M8", "M9",
            "P1", "P2", "P3",
            "S1", "S2", "S3",
        ]
        result = self.rules.aggregate_fan(hand, gold_tile="P9")
        self.assertTrue(result.complete)
        self.assertEqual(result.fan, 2)
        self.assertEqual(result.accounted_fan, 2)
        self.assertEqual(result.unresolved, ())
        self.assertEqual(
            [(item.category, item.fan) for item in result.components],
            [("gold", 2)],
        )

    def test_complete_flower_group_has_no_extra_bonus(self):
        hand = [
            "M1", "M1",
            "M2", "M3", "M4",
            "M5", "M6", "M7",
            "P1", "P2", "P3",
            "S1", "S2", "S3",
            "E", "E", "E",
        ]
        result = self.rules.aggregate_fan(
            hand, flowers=("F1", "F2", "F3", "F4")
        )
        self.assertTrue(result.complete)
        self.assertEqual(result.unresolved, ())
        self.assertEqual(result.fan, 6)  # flowers4 + honor concealed triplet2
        self.assertEqual(result.accounted_fan, 6)

    def test_eight_flowers_are_eight_ordinary_fan_after_special_pass(self):
        hand = [
            "M1", "M1",
            "M2", "M3", "M4",
            "M5", "M6", "M7",
            "P1", "P2", "P3",
            "S1", "S2", "S3",
            "E", "E", "E",
        ]
        result = self.rules.aggregate_fan(hand, flowers=tuple(env.FLOWERS))
        self.assertTrue(result.complete)
        self.assertEqual(result.unresolved, ())
        self.assertEqual(result.fan, 10)  # 8 flowers + honor concealed triplet2
        self.assertIn(("flowers", 8),
                      [(item.category, item.fan) for item in result.components])

    def test_multiple_legal_decompositions_choose_maximum_total_fan(self):
        hand = [
            "M1", "M1", "M1",
            "M2", "M2", "M2",
            "M3", "M3", "M3",
            "M4", "M4", "M4",
            "M5", "M5", "M5",
            "M6", "M6",
        ]
        result = self.rules.aggregate_fan(hand)
        self.assertTrue(result.complete)
        self.assertGreater(result.decomposition_count, 1)
        self.assertGreater(len(result.candidate_fans), 1)
        self.assertEqual(result.fan, max(result.candidate_fans))
        self.assertEqual(result.accounted_fan, result.fan)
        self.assertEqual(result.selection_policy, "MAX_TOTAL_FAN")
        self.assertIsNotNone(result.selected_decomposition_index)
        self.assertEqual(
            result.decomposition_fans[result.selected_decomposition_index],
            result.fan,
        )

    def test_exposed_peng_scoring_is_confirmed(self):
        concealed = [
            "M1", "M1",
            "M2", "M3", "M4",
            "M5", "M6", "M7",
            "P1", "P2", "P3",
            "S1", "S2", "S3",
        ]
        honor = self.rules.aggregate_fan(
            concealed, melds=(env.Meld("PENG", ["E"] * 3, 1),)
        )
        self.assertTrue(honor.complete)
        component = next(item for item in honor.components if item.category == "honor_peng")
        self.assertEqual(component.fan, 1)
        self.assertEqual(component.status, EvidenceStatus.CONFIRMED)

        suited = self.rules.aggregate_fan(
            concealed, melds=(env.Meld("PENG", ["P9"] * 3, 1),)
        )
        self.assertTrue(suited.complete)
        self.assertEqual(suited.fan, 0)
        self.assertEqual(suited.unresolved, ())
        self.assertEqual(suited.components, ())

    def test_kong_table_works_inside_aggregator(self):
        concealed = [
            "M1", "M1",
            "M2", "M3", "M4",
            "M5", "M6", "M7",
            "P1", "P2", "P3",
            "S1", "S2", "S3",
        ]
        cases = (
            ("MING_GANG", "P9", 2),
            ("MING_GANG", "E", 3),
            ("ADDED_GANG", "P9", 2),
            ("ADDED_GANG", "E", 3),
            ("AN_GANG", "P9", 3),
            ("AN_GANG", "E", 4),
        )
        for kind, tile, expected in cases:
            with self.subTest(kind=kind, tile=tile):
                source = None if kind == "AN_GANG" else 1
                result = self.rules.aggregate_fan(
                    concealed, melds=(env.Meld(kind, [tile] * 4, source),)
                )
                self.assertTrue(result.complete)
                kong = next(item for item in result.components if item.category == "kong")
                self.assertEqual(kong.fan, expected)


if __name__ == "__main__":
    unittest.main()
