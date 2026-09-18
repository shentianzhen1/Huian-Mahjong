"""Current-player qiangjin window; opponent never inherits a declined window."""
from collections import Counter
import unittest

from huian import HuianEnvironment, HuianGameState, HuianRules, HuianRulesAdapter, RulesConfig
from huian._legacy import env
from huian.rules.special_windows import working_qiangjin_eligible


GOLD = "P9"


def _fill(state):
    used = Counter(state.physical_tiles())
    reserved = []
    for tile in env.full_wall():
        have = used[tile]
        if have < 4 if tile not in env.FLOWERS else 1:
            need = (1 if tile in env.FLOWERS else 4) - have
            # flowers have 1 each in full_wall already counted via Counter of full set
            pass
    remaining = env.full_wall()
    for tile in state.physical_tiles():
        remaining.remove(tile)
    state.reserved_tiles = remaining[:-20]
    state.wall = remaining[-20:]
    return state


def two_seat_gold_state(*, current=0, current_gold=1, opponent_gold=1, current_tiles=17):
    state = HuianGameState(
        phase="OPENING_QIANGJIN_CHECK", gold_tile=GOLD, dealer=0,
        current_player=current, special_states=["NORMAL", "NORMAL"])
    idle = 16 if current_tiles == 17 else 17
    if current == 0:
        n0, n1 = current_tiles, idle
    else:
        n0, n1 = idle, current_tiles
    base0 = ["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8",
             "P1", "P2", "P3", "S1", "S2", "S3", "E", "W"]
    base1 = ["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8",
             "P1", "P2", "P3", "S1", "S2", "S4", "S", "N"]
    # honor tile "S" is invalid; use South already as S? use "S5"
    base1[-2] = "S5"
    extra0 = ["C"] if n0 == 17 else []
    extra1 = ["C"] if n1 == 17 else []
    # C invalid. Use "P4" / "P5"
    extra0 = ["P4"] if n0 == 17 else []
    extra1 = ["P5"] if n1 == 17 else []
    state.hands[0] = (base0 + extra0)[:n0]
    state.hands[1] = (base1 + extra1)[:n1]
    for _ in range(current_gold):
        state.hands[current][_] = GOLD
    opp = 1 - current
    for _ in range(opponent_gold):
        state.hands[opp][_ + 4] = GOLD
    return _fill(state)


def env_of(state, simulation=False):
    rules = HuianRulesAdapter(HuianRules(RulesConfig(
        simulation_only_normal_hand=simulation)))
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

    def test_d_sanjindao_ranks_before_qiangjin(self):
        state = two_seat_gold_state(current_gold=3, opponent_gold=0)
        self.assertTrue(HuianRules().can_sanjindao(state.hands[0], GOLD))
        types = [a.type for a in env_of(state).legal_actions()]
        self.assertEqual(types[0], env.ActionType.HU)
        first = env_of(state).legal_actions()[0]
        self.assertEqual(first.metadata.get("special"), "SANJINDAO")
        self.assertIn(env.ActionType.QIANGJIN, types)

    def test_idle_16_tiles_can_be_eligible_on_own_node_only(self):
        state = two_seat_gold_state(current=1, current_gold=1, opponent_gold=1,
                                    current_tiles=16)
        self.assertEqual(len(state.hands[1]), 16)
        self.assertTrue(working_qiangjin_eligible(state, 1))
        actions = env_of(state).legal_actions()
        self.assertTrue(any(a.type == env.ActionType.QIANGJIN and a.player == 1
                            for a in actions))
        self.assertFalse(any(a.player == 0 for a in actions))
