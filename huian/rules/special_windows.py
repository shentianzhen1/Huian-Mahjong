"""Current-player special declare windows.

Player spec 2026-09-18:
- Only added kongs are robbable; ming/an gangs are not.
- Qiangjin belongs only to the acting player after draw / flower / kong.
- Opening flip does not offer opponent qiangjin. PASS does not hand off.
- Sanjindao outranks qiangjin at the same node. With 3+ golds the player may declare immediately or PASS and continue developing the hand.
Hand-shape details for qiangjin remain UNKNOWN; eligibility here is the
working gate "gold in hand, not in Youjin" so the window ownership tests
can run without inventing a decomposition.
"""
from huian._legacy import env
from .phases import ActionReport, report as base_report, validate
from .context import DrawSource, YoujinStage

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
    if _in_youjin(state, player):
        return False
    gold = state.gold_tile
    return gold is not None and gold in state.hands[player]


def _window_just_closed(state):
    last = state.last_action
    return isinstance(last, dict) and last.get("type") == env.ActionType.PASS_QIANGJIN.value


def current_player_special_actions(adapter, state):
    p = state.current_player
    A, T = env.Action, env.ActionType
    actions = []
    # Three or more golds enter the optional Sanjindao branch first.
    # The player may declare immediately or pass and keep developing the hand.
    if adapter.rules.can_sanjindao(state.hands[p], state.gold_tile):
        return (
            A(p, T.HU, metadata={
                "win_source": "sanjindao", "special": "SANJINDAO",
                "multiplier": SANJINDAO_MULTIPLIER,
            }),
            A(p, T.PASS_QIANGJIN, metadata={
                "window": "current_only", "declined": "SANJINDAO",
                "continue_play": True,
            }),
        )
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
    # Simulation-only normal hands deliberately bypass all special Huian
    # declaration windows; keep only the confirmed Ming/An non-robbable fix.
    if adapter.rules.config.simulation_only_normal_hand:
        return _strip_unrobbable_kong_unknown(adapter, state, base_report(adapter, state))
    A, T = env.Action, env.ActionType
    p = state.current_player
    if _window_just_closed(state) and state.phase in ("AFTER_DRAW", "NEED_DRAW"):
        validate(adapter, state)
        if state.phase == "NEED_DRAW":
            return ActionReport((A(p, T.DRAW, metadata={
                "source": DrawSource.WALL_HEAD.value}),))
        return ActionReport(tuple(
            A(p, T.DISCARD, tile=tile) for tile in sorted(set(state.hands[p]))))
    if state.phase in ("OPENING_QIANGJIN_CHECK", "QIANGJIN_WINDOW"):
        validate(adapter, state)
        return ActionReport(current_player_special_actions(adapter, state))
    if state.phase in ("NEED_DRAW", "AFTER_DRAW", "AFTER_CHI", "AFTER_PENG") and (
            adapter.rules.can_sanjindao(state.hands[p], state.gold_tile)
            or working_qiangjin_eligible(state, p)):
        validate(adapter, state)
        return ActionReport(current_player_special_actions(adapter, state))
    result = base_report(adapter, state)
    result = _strip_unrobbable_kong_unknown(adapter, state, result)
    return result
