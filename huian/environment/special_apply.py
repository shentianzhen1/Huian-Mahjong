"""Transitions for current-player-only qiangjin actions."""
from huian._legacy import env


def apply_qiangjin_action(state, action):
    T = env.ActionType
    p = action.player
    if action.type == T.HU and action.metadata.get("special") == "SANJINDAO":
        state.pending_hu = {
            "winner": p,
            "source": "sanjindao",
            "gold_count": state.hands[p].count(state.gold_tile),
        }
        state.current_player = p
        state.phase = "SANJINDAO_DECLARED"
        return True
    if action.type == T.HU and action.metadata.get("special") == "EIGHT_FLOWER_YOU":
        state.pending_hu = {
            "winner": p,
            "source": "eight_flower_you",
            "flower_count": len(state.flowers[p]),
            "multiplier": action.metadata.get("multiplier"),
            "project_rule": bool(action.metadata.get("project_rule")),
        }
        state.current_player = p
        state.phase = "EIGHT_FLOWER_YOU_DECLARED"
        return True
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
