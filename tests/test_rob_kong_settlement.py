import unittest

from huian import HuianEnvironment, HuianGameState, HuianRules, HuianRulesAdapter
from huian._legacy import env


def robbed_added_kong_state():
    state = HuianGameState(
        phase="ROB_KONG_HU_DECLARED",
        gold_tile="P9",
        dealer=0,
        current_player=1,
        special_states=["NORMAL", "NORMAL"],
    )
    # Player 0 declared an ADD_KONG candidate from this original PENG.
    # The fourth M3 remains physical in hand until PASS; robbing means PASS
    # never happens and this PENG must therefore survive unchanged.
    state.melds[0] = [env.Meld("PENG", ["M3"] * 3, 1)]
    state.hands[0] = [
        "M3", "M7", "M8", "M9",
        "P4", "P5", "P6", "P7", "P8",
        "S4", "S5", "S6", "W", "W",
    ]
    # Sixteen-tile hand waiting on M3:
    # M123 / M456 / P123 / S123 / EEE / NN.
    state.hands[1] = [
        "M1", "M2", "M4", "M5", "M6",
        "P1", "P2", "P3",
        "S1", "S2", "S3",
        "E", "E", "E", "N", "N",
    ]
    state.reserved_tiles = ["P9"]
    state.pending_kong = {"kong_player": 0, "tile": "M3", "meld_index": 0}
    state.pending_hu = {
        "winner": 1,
        "loser": 0,
        "source": "rob_kong",
        "robbed_tile": "M3",
        "winning_tile": "M3",
        "kong_player": 0,
        "meld_index": 0,
    }

    remaining = env.full_wall()
    for tile in state.physical_tiles():
        remaining.remove(tile)
    state.wall = remaining
    return state


class RobKongSettlementTests(unittest.TestCase):
    def test_robbed_added_kong_never_completes_and_settles_as_zimo(self):
        instance = HuianEnvironment(HuianRulesAdapter(HuianRules()))
        instance.set_state(robbed_added_kong_state())

        before = instance.state
        self.assertEqual(before.melds[0][0].kind, "PENG")
        self.assertEqual(before.melds[0][0].tiles, ["M3"] * 3)
        self.assertEqual(before.hands[0].count("M3"), 1)
        self.assertIsNotNone(before.pending_kong)
        self.assertEqual(instance.action_report().unresolved, ())

        terminal, event = instance.finalize_ordinary_outcome(
            current_dealer_base=10
        )

        self.assertTrue(terminal.terminal)
        self.assertEqual(terminal.terminal_reason, "AUTO_ZIMO")
        self.assertEqual(terminal.melds[0][0].kind, "PENG")
        self.assertEqual(terminal.melds[0][0].tiles, ["M3"] * 3)
        self.assertEqual(terminal.hands[0].count("M3"), 1)
        self.assertFalse(any(m.kind == "ADDED_GANG" for m in terminal.melds[0]))
        self.assertIsNone(terminal.pending_kong)
        self.assertIsNone(terminal.pending_hu)

        metadata = event["action"]["metadata"]
        self.assertEqual(metadata["win_type"], "ZIMO")
        self.assertEqual(metadata["multiplier"], 2)
        self.assertEqual(metadata["hu_declaration"]["source"], "rob_kong")
        # The failed ADD_KONG belongs to the loser and must never enter the
        # winner's fan aggregation as a completed kong.
        self.assertFalse(any(
            "kong" in str(component).lower() or "gang" in str(component).lower()
            for component in metadata["fan_components"]
        ))
        self.assertEqual(sum(terminal.rewards), 0)
        self.assertGreater(terminal.rewards[1], 0)
        self.assertLess(terminal.rewards[0], 0)


if __name__ == "__main__":
    unittest.main()
