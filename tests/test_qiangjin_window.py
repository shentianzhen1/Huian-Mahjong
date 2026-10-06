"""Player-confirmed first-round Qiangjin/Tianting sequence."""
from collections import Counter
import unittest

from huian import HuianEnvironment, HuianGameState
from huian._legacy import env
from huian.rules.first_round import new_first_round_state
from huian.rules.special_windows import working_qiangjin_eligible

GOLD = "P9"
DEALER16 = [
    "M1", "M2", "M3", "M4", "M5", "M6",
    "P1", "P2", "P3", "S1", "S2", "S3",
    "E", "E", "E", GOLD,
]
NONDEALER16 = [
    "M7", "M8", "M9", "P4", "P5", "P6",
    "P7", "P8", GOLD, "S4", "S5", "S6",
    "R", "R", "R", GOLD,
]


def first_round_game(*, dealer=0, draw_tile="W", base=10):
    state = HuianGameState(
        dealer=dealer,
        current_player=dealer,
        phase="OPENING_POST_GOLD_PENDING",
        gold_tile=GOLD,
        special_states=["NORMAL", "NORMAL"],
        reserved_tiles=[GOLD],
    )
    state.hands[dealer] = [*DEALER16, "N"]
    state.hands[1 - dealer] = list(NONDEALER16)
    remaining = env.full_wall()
    for tile in state.physical_tiles():
        remaining.remove(tile)
    remaining.remove(draw_tile)
    state.wall = [draw_tile, *remaining]
    state.first_round = new_first_round_state(
        state, current_dealer_base=base
    )
    game = HuianEnvironment()
    game.set_state(state)
    return game


def advance_to_first_draw(game):
    dealer = game.state.dealer
    discard = next(
        action for action in game.legal_actions()
        if action.type == env.ActionType.DISCARD and action.tile == "N"
    )
    game.step(discard)
    self_pass = next(
        action for action in game.legal_actions()
        if action.type == env.ActionType.PASS
    )
    game.step(self_pass)
    draw = next(
        action for action in game.legal_actions()
        if action.type == env.ActionType.DRAW
    )
    game.step(draw)
    return dealer, 1 - dealer


class QiangjinFirstRoundTests(unittest.TestCase):
    def test_nondealer_tianting_is_marked_before_first_draw(self):
        for dealer in (0, 1):
            game = first_round_game(dealer=dealer)
            first = game.state.first_round
            nondealer = 1 - dealer
            self.assertTrue(first["tianting"][nondealer])
            self.assertIsNone(first["tianting"][dealer])
            self.assertTrue(first["tianting_waits"][nondealer])
            self.assertEqual(game.state.rewards, [0, 0])

    def test_dealer_first_discard_records_tianting_and_frozen_qiangjin(self):
        game = first_round_game()
        before = Counter(game.state.physical_tiles())
        discard = next(
            action for action in game.legal_actions()
            if action.type == env.ActionType.DISCARD and action.tile == "N"
        )
        state, event = game.step(discard)
        first = state.first_round
        self.assertTrue(first["dealer_first_discard_done"])
        self.assertEqual(first["dealer_first_discard_tile"], "N")
        self.assertTrue(first["tianting"][state.dealer])
        self.assertTrue(first["qiangjin_eligible"][state.dealer])
        self.assertTrue(event["action"]["metadata"]["first_round_dealer_discard"])
        self.assertEqual(before, Counter(state.physical_tiles()))

    def test_nondealer_priority_then_dealer_after_pass(self):
        for dealer in (0, 1):
            game = first_round_game(dealer=dealer)
            dealer, nondealer = advance_to_first_draw(game)
            first = game.state.first_round
            self.assertTrue(first["nondealer_first_draw_done"])
            self.assertTrue(working_qiangjin_eligible(game.state, nondealer))
            self.assertTrue(working_qiangjin_eligible(game.state, dealer))

            actions = game.legal_actions()
            self.assertTrue(actions)
            self.assertEqual({a.player for a in actions}, {nondealer})
            self.assertEqual(
                {a.type for a in actions},
                {env.ActionType.QIANGJIN, env.ActionType.PASS_QIANGJIN},
            )
            game.step(next(a for a in actions if a.type == env.ActionType.PASS_QIANGJIN))
            after = game.legal_actions()
            self.assertEqual({a.player for a in after}, {dealer})
            self.assertEqual(
                {a.type for a in after},
                {env.ActionType.QIANGJIN, env.ActionType.PASS_QIANGJIN},
            )

    def test_qiangjin_settles_normal_fan_x2_without_moving_virtual_gold(self):
        for winner_role in ("nondealer", "dealer"):
            game = first_round_game(base=15)
            dealer, nondealer = advance_to_first_draw(game)
            before = Counter(game.state.physical_tiles())
            if winner_role == "dealer":
                actions = game.legal_actions()
                game.step(next(
                    a for a in actions if a.type == env.ActionType.PASS_QIANGJIN
                ))
                actions = game.legal_actions()
                winner = dealer
            else:
                actions = game.legal_actions()
                winner = nondealer
            qj = next(a for a in actions if a.type == env.ActionType.QIANGJIN)
            terminal, event = game.step(qj)
            fan = event["action"]["metadata"]["winner_fan"]
            expected = (15 + fan) * 2
            self.assertTrue(terminal.terminal)
            self.assertEqual(terminal.rewards[winner], expected)
            self.assertEqual(terminal.rewards[1 - winner], -expected)
            self.assertEqual(sum(terminal.rewards), 0)
            self.assertEqual(before, Counter(terminal.physical_tiles()))
            self.assertEqual(terminal.reserved_tiles.count(GOLD), 1)
            metadata = event["action"]["metadata"]
            self.assertEqual(metadata["settlement_rule_id"], "settlement.qiangjin_full")
            self.assertTrue(metadata["virtual_gold"])
            self.assertFalse(metadata["physical_gold_moved"])
            self.assertEqual(metadata["multiplier"], 2)

    def test_both_pass_then_normal_play_and_no_later_qiangjin(self):
        game = first_round_game()
        dealer, nondealer = advance_to_first_draw(game)
        game.step(next(
            a for a in game.legal_actions()
            if a.type == env.ActionType.PASS_QIANGJIN
        ))
        game.step(next(
            a for a in game.legal_actions()
            if a.type == env.ActionType.PASS_QIANGJIN
        ))
        ordinary = game.legal_actions()
        self.assertTrue(ordinary)
        self.assertFalse(any(a.type == env.ActionType.QIANGJIN for a in ordinary))
        discard = next(a for a in ordinary if a.type == env.ActionType.DISCARD)
        game.step(discard)
        self.assertFalse(game.state.first_round["active"])
        # The old mid-hand gate was "Gold in hand after any draw". It must stay
        # closed even though both seats still physically hold Gold.
        self.assertFalse(working_qiangjin_eligible(game.state, dealer))
        self.assertFalse(working_qiangjin_eligible(game.state, nondealer))

    def test_imported_midhand_draw_with_gold_does_not_open_qiangjin(self):
        game = first_round_game()
        _, nondealer = advance_to_first_draw(game)
        game.state.first_round  # returned state is a copy; mutate through set_state below
        state = game.state
        state.first_round["active"] = False
        state.phase = "AFTER_DRAW"
        state.current_player = nondealer
        game.set_state(state)
        actions = game.action_report().known_actions
        self.assertFalse(any(a.type == env.ActionType.QIANGJIN for a in actions))


if __name__ == "__main__":
    unittest.main()
