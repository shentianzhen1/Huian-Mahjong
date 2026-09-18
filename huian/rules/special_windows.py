"""Current-player special declare windows.

Player spec 2026-09-18:
- Only added kongs are robbable; ming/an gangs are not.
- Qiangjin belongs only to the acting player after draw / flower / kong.
- Opening flip does not offer opponent qiangjin. PASS does not hand off.
- Sanjindao outranks qiangjin at the same node.
Hand-shape details for qiangjin remain UNKNOWN; eligibility here is the
working gate "gold in hand, not in Youjin" so the window ownership tests
can run without inventing a decomposition.
"""
from huian._legacy import env
from .phases import ActionReport, report as base_report, validate
from .context import YoujinStage

QIANGJIN_PHASES = {"OPENING_QIANGJIN_CHECK", "QIANGJIN_WINDOW", "AFTER_DRAW"}
QIANGJIN_MULTIPLIER = 4
SANJINDAO_MULTIPLIER = 3
EIGHT_FLOWER_MULTIPLIER = 8


def _in_youjin(state, player):
    stage = state.special_states[player]
    return stage in {
        YoujinStage.YOUJIN.value,
        YoujinStage.DOUBLE_YOU.value,
        YoujinStage.TRIPLE_YOU.value,
    }


def working_qiangjin_eligible(state, player):
    """Window gate only. Exact qiangjin shape is still UNKNOWN."""
    if _in_youjin(state, player):
        return False
    gold = state.gold_tile
    return gold is not None and gold in state.hands[player]


def current_player_special_actions(adapter, state):
    p = state.current_player
    A, T = env.Action, env.ActionType
    actions = []
    if adapter.rules.can_sanjindao(state.hands[p], state.gold_tile):
        actions.append(A(p, T.HU, metadata={
            "win_source": "sanjindao", "special": "SANJINDAO",
            "multiplier": SANJINDAO_MULTIPLIER,
        }))
    if working_qiangjin_eligible(state, p):
        actions.append(A(p, T.QIANGJIN, metadata={
            "win_source": "qiangjin", "multiplier": QIANGJIN_MULTIPLIER,
            "self_draw": True,
        }))
    if len(state.flowers[p]) >= 8:
        actions.append(A(p, T.HU, metadata={
            "win_source": "eight_flower_you", "special": "EIGHT_FLOWER_YOU",
            "multiplier": EIGHT_FLOWER_MULTIPLIER,
        }))
    actions.append(A(p, T.PASS_QIANGJIN, metadata={"window": "current_only"}))
    return tuple(actions)


def _strip_unrobbable_kong_unknown(adapter, state, result):
    """Ming/an gangs cannot be robbed; keep added-kong robbery only."""
    if "rob_kong" not in result.unresolved:
        return result
    unresolved = tuple(item for item in result.unresolved if item != "rob_kong")
    p = state.current_player
    A, T = env.Action, env.ActionType
    extra = []
    if state.phase == "AFTER_DRAW":
        extra.extend(
            A(p, T.AN_GANG, tile=tile, tiles=(tile,) * 4)
            for tile in adapter.rules.concealed_kongs(state.hands[p], state.gold_tile)
        )
    if state.phase == "AFTER_DISCARD" and state.pending_discard is not None:
        tile = state.pending_discard["tile"]
        options = adapter.rules.meld_options(state.hands[p], tile, state.gold_tile)
        if options.get("ming_gang"):
            extra.append(A(p, T.MING_GANG, tile=tile, tiles=(tile,) * 4))
    return ActionReport(result.known_actions + tuple(extra), unresolved)


def report_with_specials(adapter, state):
    if state.phase in ("OPENING_QIANGJIN_CHECK", "QIANGJIN_WINDOW"):
        validate(adapter, state)
        return ActionReport(current_player_special_actions(adapter, state))
    result = base_report(adapter, state)
    result = _strip_unrobbable_kong_unknown(adapter, state, result)
    if (state.phase == "AFTER_DRAW"
            and not adapter.rules.config.simulation_only_normal_hand
            and not result.unresolved):
        specials = current_player_special_actions(adapter, state)
        declares = tuple(a for a in specials if a.type != env.ActionType.PASS_QIANGJIN)
        if declares:
            return ActionReport(declares + result.known_actions)
    return result
