"""Special phase validation helpers extracted from phases.py.

This module is intentionally behavior-preserving. It validates Youjin response
phases, pending added-kong/rob-kong state, and pending Hu declarations without
owning action selection or settlement policy.
"""
from huian._legacy import env
from .context import HuContext, WinSource, YoujinStage, youjin_progression_rule


YOUJIN_RESPONSE_PHASES = {
    "YOUJIN_RESPONSE_DRAW",
    "YOUJIN_RESPONSE_AFTER_DRAW",
    "YOUJIN_STAGE_SUCCESS",
    "YOUJIN_KONG_CHOICE",
    "YOUJIN_KONG_AFTER_DRAW",
    "YOUJIN_UPGRADE_CHOICE",
    "YOUJIN_SETTLEMENT_READY",
}


def _active_youjin_players(state):
    stages = {
        YoujinStage.YOUJIN.value,
        YoujinStage.DOUBLE_YOU.value,
        YoujinStage.TRIPLE_YOU.value,
    }
    return tuple(i for i, stage in enumerate(state.special_states) if stage in stages)


def _validate_youjin_response_phase(adapter, state):
    if state.phase not in YOUJIN_RESPONSE_PHASES:
        return
    active = _active_youjin_players(state)
    if len(active) != 1:
        raise ValueError("A Youjin response phase requires exactly one active Youjin stage")
    youjin_player = active[0]
    responder = 1 - youjin_player
    if state.phase in ("YOUJIN_RESPONSE_DRAW", "YOUJIN_RESPONSE_AFTER_DRAW"):
        if state.current_player != responder:
            raise ValueError("The opponent must own the one-draw Youjin response window")
    else:
        if state.current_player != youjin_player:
            raise ValueError("Youjin progression/settlement must belong to the Youjin player")
    if state.pending_discard is not None:
        raise ValueError("Youjin chain does not use an ordinary discard-claim window")
    if state.phase == "YOUJIN_RESPONSE_AFTER_DRAW":
        last = state.last_action
        if (not isinstance(last, dict)
                or last.get("type") != env.ActionType.DRAW.value
                or last.get("player") != responder):
            raise ValueError("Youjin response-after-draw requires the opponent draw event")
    if state.phase == "YOUJIN_STAGE_SUCCESS":
        last = state.last_action
        metadata = last.get("metadata", {}) if isinstance(last, dict) else {}
        if (not isinstance(last, dict)
                or last.get("type") != env.ActionType.DISCARD.value
                or last.get("player") != responder
                or metadata.get("youjin_response_discard") is not True):
            raise ValueError(
                "Youjin stage success requires the opponent's mandatory response discard"
            )
    if state.phase == "YOUJIN_KONG_CHOICE":
        if state.special_states[youjin_player] == YoujinStage.TRIPLE_YOU.value:
            raise ValueError("Triple-You has no own progression draw/kong choice")
        last = state.last_action
        metadata = last.get("metadata", {}) if isinstance(last, dict) else {}
        if (not isinstance(last, dict)
                or last.get("type") != env.ActionType.DRAW.value
                or last.get("player") != youjin_player
                or metadata.get("youjin_progression")
                    != state.special_states[youjin_player]):
            raise ValueError(
                "Youjin kong choice requires the completed own progression draw"
            )
    if state.phase == "YOUJIN_KONG_AFTER_DRAW":
        last = state.last_action
        try:
            context = HuContext.from_draw_metadata(
                last.get("metadata", {}) if isinstance(last, dict) else {}
            )
        except (AttributeError, ValueError) as exc:
            raise ValueError(
                "Youjin kong continuation requires an audited kong-tail draw"
            ) from exc
        if (not isinstance(last, dict)
                or last.get("player") != youjin_player
                or context.source != WinSource.KONG_TAIL_DRAW):
            raise ValueError(
                "Youjin kong continuation requires the owner's kong-tail draw"
            )
    if state.phase == "YOUJIN_UPGRADE_CHOICE":
        if state.special_states[youjin_player] == YoujinStage.TRIPLE_YOU.value:
            raise ValueError("Triple-You has no further upgrade choice")
        if not adapter.rules.can_youjin_upgrade_after_draw(
                state.hands[youjin_player], state.gold_tile,
                len(state.melds[youjin_player])):
            raise ValueError("Youjin upgrade choice requires a structurally free gold")
    if state.phase == "YOUJIN_SETTLEMENT_READY":
        # Single/Double settlement follows the Youjin player's extra draw.
        # Triple settlement follows the opponent's mandatory response discard.
        stage = YoujinStage(state.special_states[youjin_player])
        expected_last_player = (
            responder if stage == YoujinStage.TRIPLE_YOU else youjin_player
        )
        last = state.last_action
        if (not isinstance(last, dict)
                or last.get("player") != expected_last_player):
            raise ValueError("Youjin settlement phase has inconsistent transition provenance")


def _validate_pending_kong(state):
    pending = getattr(state, "pending_kong", None)
    if state.phase not in ("ROB_KONG_WINDOW", "ROB_KONG_HU_DECLARED"):
        if pending is not None:
            raise ValueError("Pending kong outside its response/declaration phase")
        return
    if not isinstance(pending, dict) or set(pending) != {"kong_player", "tile", "meld_index"}:
        raise ValueError("A rob-kong phase requires a complete pending kong reference")
    player, index, tile = pending["kong_player"], pending["meld_index"], pending["tile"]
    if type(player) is not int or player not in (0, 1) or state.current_player != 1 - player:
        raise ValueError("The opponent must respond to an added kong")
    if type(index) is not int or not 0 <= index < len(state.melds[player]):
        raise ValueError("Invalid pending kong meld index")
    meld = state.melds[player][index]
    if (tile not in env.BASE_TILES or tile == state.gold_tile or meld.kind != "PENG"
            or meld.tiles != [tile] * 3 or state.hands[player].count(tile) != 1):
        raise ValueError("Pending kong must retain its original pung and fourth hand tile")
    if state.pending_discard is not None:
        raise ValueError("A rob-kong window cannot also claim a river discard")


def _validate_rob_kong_hu(state):
    pending = state.pending_kong
    player = pending["kong_player"]
    expected = {"winner": 1 - player, "loser": player, "source": WinSource.ROB_KONG.value,
                "robbed_tile": pending["tile"], "winning_tile": pending["tile"],
                "kong_player": player, "meld_index": pending["meld_index"]}
    hu = state.pending_hu
    if (not isinstance(hu, dict) or hu != expected
            or any(type(hu.get(name)) is not int
                   for name in ("winner", "loser", "kong_player", "meld_index"))):
        raise ValueError("Rob-kong Hu must reference the pending kong without moving its tile")


def _validate_added_kong_phase(state):
    last = state.last_action
    p = state.current_player
    if (not isinstance(last, dict) or last.get("type") != env.ActionType.PASS.value
            or type(last.get("player")) is not int or last["player"] != 1 - p):
        raise ValueError("Added-kong completion requires its opponent's PASS")
    metadata = last.get("metadata")
    if not isinstance(metadata, dict) or set(metadata) != {"kong_player", "tile", "meld_index"}:
        raise ValueError("Added-kong completion requires the indexed PASS audit reference")
    index, tile = metadata["meld_index"], metadata["tile"]
    if (type(metadata["kong_player"]) is not int or metadata["kong_player"] != p
            or type(index) is not int or not 0 <= index < len(state.melds[p])):
        raise ValueError("Invalid completed added-kong reference")
    meld = state.melds[p][index]
    if meld.kind != "ADDED_GANG" or meld.tiles != [tile] * 4 or tile in state.hands[p]:
        raise ValueError("The indexed original pung must now be the added kong")


def _validate_pending_hu(state):
    pending = state.pending_hu
    if state.phase == "ROB_KONG_HU_DECLARED":
        _validate_rob_kong_hu(state)
        return
    if state.phase == "QIANGJIN_DECLARED":
        if (not isinstance(pending, dict)
                or set(pending) != {"winner", "source"}
                or pending["source"] != "qiangjin"
                or type(pending["winner"]) is not int
                or pending["winner"] not in (0, 1)
                or pending["winner"] != state.current_player):
            raise ValueError("QIANGJIN_DECLARED requires a valid current-player declaration")
        return
    if state.phase == "SANJINDAO_DECLARED":
        if (not isinstance(pending, dict)
                or set(pending) != {"winner", "source", "gold_count"}
                or pending["source"] != "sanjindao"
                or type(pending["winner"]) is not int
                or pending["winner"] not in (0, 1)
                or pending["winner"] != state.current_player
                or type(pending["gold_count"]) is not int
                or pending["gold_count"] != 3):
            raise ValueError("SANJINDAO_DECLARED requires an exact third-gold declaration")
        if state.gold_tile is None or state.hands[pending["winner"]].count(state.gold_tile) != 3:
            raise ValueError("Sanjindao declaration must retain exactly three gold tiles")
        return
    if state.phase == "EIGHT_FLOWER_YOU_DECLARED":
        expected = {"winner", "source", "flower_count", "fixed_fan",
                    "multiplier", "project_rule"}
        if (not isinstance(pending, dict) or set(pending) != expected
                or pending["source"] != "eight_flower_you"
                or type(pending["winner"]) is not int
                or pending["winner"] not in (0, 1)
                or pending["winner"] != state.current_player
                or pending["flower_count"] != 8
                or pending["fixed_fan"] != 16
                or pending["multiplier"] != 1
                or pending["project_rule"] is not True):
            raise ValueError(
                "EIGHT_FLOWER_YOU_DECLARED requires fixed 16 fan and no extra multiplier"
            )
        if len(state.flowers[pending["winner"]]) != 8:
            raise ValueError("Eight-flower declaration must retain all eight flowers")
        return
    if state.phase != "HU_DECLARED":
        if pending is not None:
            raise ValueError("Pending Hu outside a declaration phase")
        return
    keys = {"winner", "source", "winning_tile", "kong_kind",
            "discard_player", "river_index"}
    if not isinstance(pending, dict) or set(pending) != keys:
        raise ValueError("HU_DECLARED requires a complete pending Hu reference")
    winner = pending["winner"]
    if type(winner) is not int or winner not in (0, 1) or winner != state.current_player:
        raise ValueError("Invalid pending Hu winner")
    try:
        source = WinSource(pending["source"])
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid pending Hu source") from exc
    if source == WinSource.ROB_KONG:
        raise ValueError("Rob-kong Hu requires its dedicated declaration phase")
    tile = pending["winning_tile"]
    if tile is not None and tile not in env.BASE_TILES:
        raise ValueError("Invalid pending Hu winning tile")
    kind = pending["kong_kind"]
    if source == WinSource.KONG_TAIL_DRAW:
        if kind not in ("MING_GANG", "AN_GANG", "ADDED_GANG"):
            raise ValueError("Gang-Hu must record its kong kind")
    elif kind is not None:
        raise ValueError("Only Gang-Hu may record a kong kind")
    if source == WinSource.DISCARD:
        player, index = pending["discard_player"], pending["river_index"]
        if player != 1 - winner or type(index) is not int:
            raise ValueError("Invalid discard Hu source reference")
        river = state.discards[player]
        if index < 0 or index >= len(river) or river[index] != tile:
            raise ValueError("Discard Hu must reference its source river tile")
    else:
        if pending["discard_player"] is not None or pending["river_index"] is not None:
            raise ValueError("Self-draw Hu cannot reference a discard")
        if tile is None or tile not in state.hands[winner]:
            raise ValueError("Self-draw Hu tile must remain in the winner's hand")


