"""Current-player qiangjin window; opponent never inherits a declined window."""
from collections import Counter
import unittest

from huian import HuianEnvironment, HuianGameState, HuianRules, HuianRulesAdapter, RulesConfig
from huian._legacy import env
from huian.rules.special_windows import working_qiangjin_eligible


GOLD = "P9"


def _fill(state):
    remaining = env.full_wall()
    for tile in list(state.physical_tiles()):
        remaining.remove(tile)
    state.reserved_tiles = remaining[:-20]
    state.wall = remaining[-20:]
    assert Counter(state.physical_tiles()) == Counter(env.full_wall())
    return state


def two_seat_gold_state(*, current=0, current_gold=1, opponent_gold=1,
                        current_tiles=17, phase="OPENING_QIANGJIN_CHECK"):
    state = HuianGameState(
        phase=phase, gold_tile=GOLD, dealer=0,
        current_player=current, special_states=["NORMAL", "NORMAL"])
    # At a normal NEED_DRAW node both players may be on 16 concealed tiles;
    # only the opening dealer starts with 17.
    other_tiles = 16
    if current == 0:
        n0, n1 = current_tiles, other_tiles
    else:
        n0, n1 = other_tiles, current_tiles
    base0 = ["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8",
             "P1", "P2", "P3", "S1", "S2", "S3", "E", "W"]
    base1 = ["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8",
             "P1", "P2", "P3", "S1", "S2", "S4", "SOUTH", "N"]
    extra0 = ["P4"] if n0 == 17 else []
    extra1 = ["P5"] if n1 == 17 else []
    state.hands[0] = (base0 + extra0)[:n0]
    state.hands[1] = (base1 + extra1)[:n1]
    for index in range(current_gold):
        state.hands[current][index] = GOLD
    opp = 1 - current
    for index in range(opponent_gold):
        state.hands[opp][index + 4] = GOLD
    return _fill(state)


def mark_third_gold_draw(state):
    state.phase = "AFTER_DRAW"
    state.last_action = env.Action(
        state.current_player, env.ActionType.DRAW,
        metadata={"source": "wall_head", "drawn_tile": GOLD},
    ).to_dict()
    return state


def env_of(state):
    rules = HuianRulesAdapter(HuianRules(RulesConfig()))
    game = HuianEnvironment(rules=rules)
    game.set_state(state)
    return game


class QiangjinWindowTests(unittest.TestCase):
    def test_a_current_pass_does_not_hand_off_to_eligible_opponent(self):
        state = two_seat_gold_state(current_gold=1, opponent_gold=1)
        self.assertTrue(working_qiangjin_eligible(state, 0))
        self.assertTrue(working_qiangjin_eligible(state, 1))
        game = env_of(state)
        actions = game.legal_actions()
        self.assertTrue(any(a.type == env.ActionType.QIANGJIN and a.player == 0
                            for a in actions))
        self.assertFalse(any(a.player == 1 for a in actions))
        pass_act = next(a for a in actions if a.type == env.ActionType.PASS_QIANGJIN)
        game.step(pass_act)
        after = game.legal_actions()
        self.assertFalse(any(a.type == env.ActionType.QIANGJIN and a.player == 1
                             for a in after))
        self.assertTrue(all(a.player == 0 for a in after))

    def test_b_opponent_only_eligible_does_not_open_window(self):
        state = two_seat_gold_state(current_gold=0, opponent_gold=1)
        self.assertFalse(working_qiangjin_eligible(state, 0))
        self.assertTrue(working_qiangjin_eligible(state, 1))
        actions = env_of(state).legal_actions()
        self.assertFalse(any(a.type == env.ActionType.QIANGJIN for a in actions))
        self.assertTrue(any(a.type == env.ActionType.PASS_QIANGJIN and a.player == 0
                            for a in actions))

    def test_c_pass_qiangjin_requires_discard(self):
        state = two_seat_gold_state(current_gold=1, opponent_gold=0)
        game = env_of(state)
        pass_act = next(a for a in game.legal_actions()
                        if a.type == env.ActionType.PASS_QIANGJIN)
        game.step(pass_act)
        actions = game.legal_actions()
        self.assertTrue(actions)
        self.assertTrue(all(a.type == env.ActionType.DISCARD and a.player == 0
                            for a in actions))

    def test_d_sanjindao_is_optional_only_on_third_gold_draw(self):
        state = mark_third_gold_draw(two_seat_gold_state(
            current_gold=3, opponent_gold=0, phase="AFTER_DRAW"))
        self.assertTrue(HuianRules().can_sanjindao(
            state.hands[0], GOLD, third_gold_just_received=True))
        game = env_of(state)
        actions = game.legal_actions()
        self.assertEqual(actions[0].metadata.get("special"), "SANJINDAO")
        self.assertFalse(any(a.type == env.ActionType.QIANGJIN for a in actions))
        pass_act = next(a for a in actions if a.type == env.ActionType.PASS_QIANGJIN)
        self.assertTrue(pass_act.metadata.get("continue_play"))
        game.step(pass_act)
        after = game.legal_actions()
        self.assertTrue(after)
        self.assertTrue(all(a.type == env.ActionType.DISCARD for a in after))

    def test_sanjindao_declaration_stops_only_at_unknown_settlement(self):
        state = mark_third_gold_draw(two_seat_gold_state(
            current_gold=3, opponent_gold=0, phase="AFTER_DRAW"))
        game = env_of(state)
        declare = next(a for a in game.legal_actions()
                       if a.metadata.get("special") == "SANJINDAO")
        game.step(declare)
        self.assertEqual(game.state.phase, "SANJINDAO_DECLARED")
        with self.assertRaisesRegex(RuntimeError, "sanjindao_settlement"):
            game.legal_actions()

    def test_existing_three_gold_does_not_reopen_sanjindao(self):
        state = two_seat_gold_state(
            current=1, current_gold=3, opponent_gold=0, current_tiles=16,
            phase="NEED_DRAW")
        game = env_of(state)
        actions = game.legal_actions()
        self.assertFalse(any(
            a.metadata.get("special") == "SANJINDAO" for a in actions
        ))
        self.assertTrue(any(a.type == env.ActionType.QIANGJIN for a in actions))

    def test_idle_16_tiles_can_be_eligible_on_own_node_only(self):
        state = two_seat_gold_state(
            current=1, current_gold=1, opponent_gold=1, current_tiles=16,
            phase="NEED_DRAW")
        self.assertEqual(len(state.hands[1]), 16)
        self.assertTrue(working_qiangjin_eligible(state, 1))
        actions = env_of(state).legal_actions()
        self.assertTrue(any(a.type == env.ActionType.QIANGJIN and a.player == 1
                            for a in actions))
        self.assertFalse(any(a.player == 0 for a in actions))
