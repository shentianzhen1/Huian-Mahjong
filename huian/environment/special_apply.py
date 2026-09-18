"""Transitions for current-player-only qiangjin actions."""
from huian._legacy import env


def apply_qiangjin_action(state, action):
    T = env.ActionType
    p = action.player
    if action.type == T.PASS_QIANGJIN:
        expected = 16 - 3 * len(state.melds[p])
        state.phase = "AFTER_DRAW" if len(state.hands[p]) > expected else "NEED_DRAW"
        return True
    if action.type == T.QIANGJIN:
        state.pending_hu = {
            "winner": p,
            "source": "self_draw",
            "winning_tile": state.gold_tile,
            "kong_kind": None,
            "discard_player": None,
            "river_index": None,
        }
        state.current_player = p
        state.phase = "HU_DECLARED"
        return True
    return False
