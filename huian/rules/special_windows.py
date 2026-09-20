"""Current-player special declare windows.

Player spec 2026-09-18:
- ADD_KONG = 补杠/蓄杠/加杠: an existing Peng upgraded with a self-drawn fourth tile. It is an exposed-kong subtype and is the only robbable kong.
- MING_GANG = 大明杠: opponent discard + three matching hand tiles; not robbable.
- AN_GANG = 暗杠: four matching concealed tiles; not robbable.
- Qiangjin belongs only to the acting player after draw / flower / kong.
- Opening flip does not offer opponent qiangjin. PASS does not hand off.
- Sanjindao outranks qiangjin at an eligible current-player prompt. The opened gold indicator consumes one physical copy, so three playable golds is the maximum. Opening 3 gold and the first 2->3 gold draw are confirmed entry forms. New replay evidence shows PASS closes only the current prompt: a later own draw while still holding all 3 playable golds can offer Sanjindao again.
Hand-shape details for qiangjin remain UNKNOWN; eligibility here is the
working gate "gold in hand, not in Youjin" so the window ownership tests
can run without inventing a decomposition.
"""
from huian._legacy import env
from .phases import ActionReport, report as base_report, validate
from .context import DrawSource, YoujinStage
from .special_outcomes import special_outcome_profile


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


def _last_effective_draw(state, player):
    last = state.last_action
    if (not isinstance(last, dict)
            or last.get("type") != env.ActionType.DRAW.value
            or last.get("player") != player):
        return None
    metadata = last.get("metadata") or {}
    return metadata.get("effective_drawn_tile", metadata.get("drawn_tile"))


def _just_received_third_gold(state, player):
    gold = state.gold_tile
    return (gold is not None
            and state.hands[player].count(gold) == 3
            and _last_effective_draw(state, player) == gold)


def _opening_sanjindao_check(state, player):
    gold = state.gold_tile
    return (
        state.phase == "OPENING_QIANGJIN_CHECK"
        and gold is not None
        and state.hands[player].count(gold) == 3
    )


def _later_sanjindao_draw_check(state, player):
    """Later own-draw re-check after a prior Sanjindao PASS.

    match_evidence_002/player clarification shows repeated optional prompts while
    all three playable golds remain. A fourth playable gold is physically
    impossible because the opened indicator is the fourth copy.
    """
    gold = state.gold_tile
    last = state.last_action
    return (
        gold is not None
        and state.hands[player].count(gold) == 3
        and isinstance(last, dict)
        and last.get("type") == env.ActionType.DRAW.value
        and last.get("player") == player
    )


def _just_completed_eight_flowers(state, player):
    if len(state.flowers[player]) != 8:
        return False
    if state.phase == "OPENING_QIANGJIN_CHECK":
        return True
    last = state.last_action
    if (not isinstance(last, dict)
            or last.get("type") != env.ActionType.DRAW.value
            or last.get("player") != player):
        return False
    metadata = last.get("metadata") or {}
    return metadata.get("drawn_tile") in env.FLOWERS


def current_player_special_actions(adapter, state):
    p = state.current_player
    A, T = env.Action, env.ActionType
    actions = []
    # Sanjindao PASS closes only the current prompt. A later own draw with
    # exactly three golds can offer the choice again.
    third_gold = _just_received_third_gold(state, p)
    opening_check = _opening_sanjindao_check(state, p)
    later_draw_check = _later_sanjindao_draw_check(state, p) and not third_gold
    if adapter.rules.can_sanjindao(
            state.hands[p], state.gold_tile,
            third_gold_just_received=third_gold,
            opening_check=opening_check,
            later_draw_check=later_draw_check):
        profile = special_outcome_profile("SANJINDAO")
        return (
            A(p, T.HU, metadata={
                "win_source": "sanjindao",
                **profile.action_metadata,
            }),
            A(p, T.PASS_QIANGJIN, metadata={
                "window": "current_only", "declined": "SANJINDAO",
                "continue_play": True,
            }),
        )
    if working_qiangjin_eligible(state, p):
        profile = special_outcome_profile("QIANGJIN")
        actions.append(A(p, T.QIANGJIN, metadata={
            "win_source": "qiangjin",
            "self_draw": True,
            **profile.action_metadata,
        }))
    if _just_completed_eight_flowers(state, p):
        profile = special_outcome_profile("EIGHT_FLOWER_YOU")
        actions.append(A(p, T.HU, metadata={
            "win_source": "eight_flower_you",
            **profile.action_metadata,
        }))
    actions.append(A(p, T.PASS_QIANGJIN, metadata={"window": "current_only"}))
    return tuple(actions)


def _single_youjin_offer_actions(adapter, state):
    """Known optional single-Youjin declarations after the current special window.

    A distinct YOUJIN action records the system's special choice. Ordinary
    DISCARD of the same tile remains available and means the player declined
    this offer without locking future Youjin-family progression.
    """
    p = state.current_player
    candidates = adapter.rules.youjin_entry_discards(
        state.hands[p], state.gold_tile, len(state.melds[p])
    )
    A, T = env.Action, env.ActionType
    return tuple(
        A(p, T.YOUJIN, tile=tile, metadata={
            "stage": YoujinStage.YOUJIN.value,
            "optional": True,
            "entry_rule": "complete_melds_plus_one_roaming_gold",
        })
        for tile in candidates
    )


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
    # Simulation-only hands bypass special Huian declaration windows by
    # default. A narrow research opt-in can expose only confirmed Youjin-family
    # actions while Qiangjin/Sanjindao/Eight-Flower stay on their PASS path.
    # ADD_KONG (补/蓄/加杠) remains the only robbable kong branch.
    if adapter.rules.config.simulation_only_normal_hand:
        result = _strip_unrobbable_kong_unknown(
            adapter, state, base_report(adapter, state)
        )
        if not adapter.rules.config.simulation_enable_youjin:
            return result

        # Established Youjin phases are already fully described by base_report.
        if (state.special_states != ["NORMAL", "NORMAL"]
                or state.phase.startswith("YOUJIN_")):
            return result

        # Single-Youjin offers are exposed only after an auditable real own draw.
        # The synthetic opening bypass is not treated as evidence of an opening
        # Youjin window.
        last = state.last_action
        if (state.phase == "AFTER_DRAW"
                and isinstance(last, dict)
                and last.get("type") == env.ActionType.DRAW.value
                and last.get("player") == state.current_player):
            youjin = _single_youjin_offer_actions(adapter, state)
            if youjin:
                return ActionReport(
                    youjin + result.known_actions, result.unresolved
                )
        return result
    A, T = env.Action, env.ActionType
    p = state.current_player
    if _window_just_closed(state) and state.phase in ("AFTER_DRAW", "NEED_DRAW"):
        validate(adapter, state)
        if state.phase == "NEED_DRAW":
            return ActionReport((A(p, T.DRAW, metadata={
                "source": DrawSource.WALL_HEAD.value}),))
        youjin = _single_youjin_offer_actions(adapter, state)
        discards = tuple(
            A(p, T.DISCARD, tile=tile) for tile in sorted(set(state.hands[p])))
        return ActionReport(youjin + discards)
    if state.phase == "OPENING_QIANGJIN_CHECK":
        validate(adapter, state)
        return ActionReport(current_player_special_actions(adapter, state))
    # Mid-hand special windows exist only after the acting player has completed
    # a real draw. Flower replacement and all three kong replacement draws are
    # recorded as that same DRAW event (with effective_drawn_tile / wall_tail
    # metadata), so they pass this gate without making NEED_DRAW, CHI, or PENG
    # nodes spuriously eligible.
    if state.phase == "AFTER_DRAW" and _last_effective_draw(state, p) is not None and (
            _just_received_third_gold(state, p)
            or _later_sanjindao_draw_check(state, p)
            or _just_completed_eight_flowers(state, p)
            or working_qiangjin_eligible(state, p)):
        validate(adapter, state)
        return ActionReport(current_player_special_actions(adapter, state))
    result = base_report(adapter, state)
    result = _strip_unrobbable_kong_unknown(adapter, state, result)
    return result
