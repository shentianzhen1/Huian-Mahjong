"""Action-to-state transition implementation for HuianEnvironment.

This module is a behavior-preserving extraction from HuianEnvironment._apply.
It owns no legality decisions; callers must continue to authorize actions before
calling it.
"""
from huian._legacy import env
from huian.rules.context import (
    DrawSource,
    WinSource,
    YoujinStage,
    youjin_progression_rule,
)


def apply_action(state, action):
    p, kind = action.player, action.type
    T = env.ActionType
    if kind == T.DRAW:
        response_draw = state.phase == "YOUJIN_RESPONSE_DRAW"
        progression_draw = state.phase == "YOUJIN_STAGE_SUCCESS"
        source = DrawSource.parse(action.metadata.get("source"))
        tile = state.wall.pop(-1 if source == DrawSource.WALL_TAIL else 0)
        action.metadata["drawn_tile"] = tile
        state.hands[p].append(tile)
        if tile in env.FLOWERS:
            state.phase = "NEED_FLOWER_REPLACE"
        elif response_draw:
            state.phase = "YOUJIN_RESPONSE_AFTER_DRAW"
        elif progression_draw:
            state.phase = "AFTER_DRAW"
        else:
            state.phase = "AFTER_DRAW"
    elif kind == T.PASS:
        if state.phase == "YOUJIN_KONG_AFTER_DRAW":
            if not action.metadata.get("youjin_kong_tail_settle"):
                raise ValueError(
                    "Youjin Kong-tail PASS must explicitly choose special settlement"
                )
            state.phase = "YOUJIN_SETTLEMENT_READY"
            return
        if state.phase == "YOUJIN_KONG_CHOICE":
            if not action.metadata.get("youjin_kong_decline"):
                raise ValueError("Youjin Kong PASS must explicitly decline Kong")
            state.phase = "AFTER_DRAW"
            return
        if state.phase == "YOUJIN_UPGRADE_CHOICE":
            if not action.metadata.get("youjin_upgrade_decline"):
                raise ValueError("Youjin upgrade PASS must explicitly decline upgrade")
            state.phase = "YOUJIN_SETTLEMENT_READY"
            return
        if state.phase == "ROB_KONG_WINDOW":
            pending = state.pending_kong
            kong_player, tile = pending["kong_player"], pending["tile"]
            meld = state.melds[kong_player][pending["meld_index"]]
            state.hands[kong_player].remove(tile)
            state.melds[kong_player][pending["meld_index"]] = env.Meld(
                "ADDED_GANG", list(meld.tiles) + [tile], meld.from_player)
            action.metadata.update(pending)
            state.pending_kong = None
            state.current_player = kong_player
            state.phase = "AFTER_ADDED_GANG"
            return
        # DISCARD already selected the sole opponent as current_player.
        # The declined tile stays in its owner's river.
        state.pending_discard = None
        state.phase = "NEED_DRAW"
    elif kind == T.YOUJIN:
        state.hands[p].remove(action.tile)
        state.discards[p].append(action.tile)
        state.pending_discard = None
        state.special_states[p] = "YOUJIN"
        state.current_player = 1 - p
        state.phase = "YOUJIN_RESPONSE_DRAW"
    elif kind in (T.DOUBLE_YOU, T.TRIPLE_YOU):
        if state.phase not in (
                "YOUJIN_UPGRADE_CHOICE", "YOUJIN_KONG_AFTER_DRAW"):
            raise ValueError("Youjin upgrade action requires an upgrade-capable phase")
        current = YoujinStage(state.special_states[p])
        progression = youjin_progression_rule(current)
        expected = (
            YoujinStage.DOUBLE_YOU if kind == T.DOUBLE_YOU
            else YoujinStage.TRIPLE_YOU
        )
        if progression.next_stage != expected:
            raise ValueError("Youjin upgrade does not match the next confirmed stage")
        if action.tile != state.gold_tile:
            raise ValueError("Youjin upgrade must discard one current gold tile")
        state.hands[p].remove(state.gold_tile)
        state.discards[p].append(state.gold_tile)
        state.pending_discard = None
        state.special_states[p] = expected.value
        state.current_player = 1 - p
        state.phase = "YOUJIN_RESPONSE_DRAW"
    elif kind == T.DISCARD:
        if state.phase == "YOUJIN_KONG_AFTER_DRAW":
            if action.metadata.get("youjin_kong_discard") is not True:
                raise ValueError(
                    "Youjin Kong-tail continuation requires its special discard"
                )
            if action.tile == state.gold_tile:
                raise ValueError(
                    "Discarding Jin from a Youjin Kong tail must use the upgrade action"
                )
            state.hands[p].remove(action.tile)
            state.discards[p].append(action.tile)
            state.pending_discard = None
            state.current_player = 1 - p
            state.phase = "YOUJIN_RESPONSE_DRAW"
        elif state.phase == "YOUJIN_RESPONSE_AFTER_DRAW":
            if action.metadata.get("youjin_response_discard") is not True:
                raise ValueError(
                    "Missed Youjin response requires an explicit response discard"
                )
            youjin_player = 1 - p
            stage = YoujinStage(state.special_states[youjin_player])
            progression = youjin_progression_rule(stage)
            state.hands[p].remove(action.tile)
            state.discards[p].append(action.tile)
            state.pending_discard = None
            state.current_player = youjin_player
            state.phase = (
                "YOUJIN_SETTLEMENT_READY"
                if progression.youjin_player_draw_chances == 0
                else "YOUJIN_STAGE_SUCCESS"
            )
        else:
            state.hands[p].remove(action.tile)
            state.discards[p].append(action.tile)
            state.pending_discard = dict(player=p, tile=action.tile,
                                         river_index=len(state.discards[p]) - 1)
            state.current_player = 1 - p
            state.phase = "AFTER_DISCARD"
    elif kind == T.ADD_KONG:
        state.pending_kong = {
            "kong_player": p, "tile": action.tile,
            "meld_index": action.metadata["meld_index"],
        }
        state.current_player = 1 - p
        state.phase = "ROB_KONG_WINDOW"
    elif kind == T.ROB_KONG_HU:
        pending = state.pending_kong
        state.pending_hu = {
            "winner": p, "loser": pending["kong_player"],
            "source": WinSource.ROB_KONG.value, "robbed_tile": action.tile,
            "winning_tile": action.tile, "kong_player": pending["kong_player"],
            "meld_index": pending["meld_index"],
        }
        state.current_player = p
        state.phase = "ROB_KONG_HU_DECLARED"
    elif kind == T.HU:
        if state.phase == "YOUJIN_RESPONSE_AFTER_DRAW":
            youjin_player = 1 - p
            state.special_states[youjin_player] = "NORMAL"
        source = WinSource(action.metadata.get("win_source"))
        pending = state.pending_discard if source == WinSource.DISCARD else None
        state.pending_hu = {
            "winner": p,
            "source": source.value,
            "winning_tile": action.tile,
            "kong_kind": action.metadata.get("kong_kind"),
            "discard_player": pending["player"] if pending else None,
            "river_index": pending["river_index"] if pending else None,
        }
        state.pending_discard = None
        state.current_player = p
        state.phase = "HU_DECLARED"
    elif kind in (T.CHI, T.PENG, T.MING_GANG, T.AN_GANG):
        consume = list(action.tiles)
        source = None
        if kind != T.AN_GANG:
            pending = state.pending_discard
            source = pending["player"]
            consume.remove(pending["tile"])
            state.discards[source].pop(pending["river_index"])
            state.pending_discard = None
        for tile in consume:
            state.hands[p].remove(tile)
        state.melds[p].append(env.Meld(kind.value, list(action.tiles), source))
        state.phase = "AFTER_" + kind.value
    else:
        raise ValueError("Unsupported transition")

