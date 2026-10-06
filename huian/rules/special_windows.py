"""Current-player special declare windows.

Confirmed 2026-10-06 correction:
- Qiangjin exists only in the first round after opening replacement + Gold.
- Dealer eligibility is frozen after the dealer's first discard (remaining 16 +
  the single reserved opened Gold, virtually, for a 17-tile Hu analysis).
- Nondealer eligibility is frozen after the first draw by virtually replacing
  exactly that drawn tile with the reserved opened Gold; the hand stays 17.
- Nondealer has priority. Dealer can act only after nondealer is ineligible or
  explicitly passes. No later draw, flower replacement or Kong draw reopens it.
- Qiangjin uses ordinary fan and ordinary self-draw x2 settlement.

Sanjindao repeated own-draw prompts and Eight-Flower windows remain independent.
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
    """Compatibility name backed by confirmed first-round provenance only."""
    first = getattr(state, "first_round", None)
    return bool(
        isinstance(first, dict)
        and first.get("active")
        and player in (0, 1)
        and first["qiangjin_eligible"][player]
        and not first["qiangjin_resolved"][player]
    )


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
        state.phase in ("OPENING_QIANGJIN_CHECK", "OPENING_POST_GOLD_PENDING")
        and player == state.dealer
        and gold is not None
        and state.hands[player].count(gold) == 3
    )


def _later_sanjindao_draw_check(state, player):
    """Later own-draw re-check after a prior Sanjindao PASS."""
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
    """Non-Qiangjin current-seat special choices in confirmed priority order."""
    p = state.current_player
    A, T = env.Action, env.ActionType
    # Same-node confirmed order: Eight-Flower before Sanjindao. Qiangjin is
    # first-round-only and is injected separately with nondealer seat priority.
    if _just_completed_eight_flowers(state, p):
        profile = special_outcome_profile("EIGHT_FLOWER_YOU")
        return (
            A(p, T.HU, metadata={
                "win_source": "eight_flower_you",
                **profile.action_metadata,
            }),
            A(p, T.PASS_QIANGJIN, metadata={
                "window": "current_only", "declined": "EIGHT_FLOWER_YOU",
                "continue_play": True,
            }),
        )
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
    return ()


def _first_round_qiangjin_actions(state, player):
    first = state.first_round
    role = (
        "dealer_after_first_discard"
        if player == state.dealer
        else "nondealer_after_first_draw"
    )
    profile = special_outcome_profile("QIANGJIN")
    metadata = {
        "win_source": "qiangjin",
        "window": "first_round",
        "role": role,
        "seat_priority": "NONDEALER_THEN_DEALER",
        "winner_fan": first["qiangjin_fan"][player],
        "current_dealer_base": first["current_dealer_base"],
        "virtual_gold": True,
        "physical_gold_moved": False,
        **profile.action_metadata,
    }
    return (
        env.Action(player, env.ActionType.QIANGJIN, metadata=metadata),
        env.Action(player, env.ActionType.PASS_QIANGJIN, metadata={
            "window": "first_round",
            "role": role,
            "declined": "QIANGJIN",
            "seat_priority": "NONDEALER_THEN_DEALER",
        }),
    )


def _first_round_report(adapter, state):
    first = getattr(state, "first_round", None)
    if not isinstance(first, dict) or not first.get("active"):
        return None
    validate(adapter, state)
    dealer = state.dealer
    nondealer = 1 - dealer

    # After Gold/Tianhu, dealer must make the first discard. Opening Sanjindao
    # remains higher priority if actually legal. A prior PASS at this same node
    # is not re-offered immediately.
    if (state.current_player == dealer
            and not first.get("dealer_first_discard_done")
            and state.phase in ("OPENING_POST_GOLD_PENDING", "AFTER_DRAW")):
        last = state.last_action
        declined_sanjindao = (
            isinstance(last, dict)
            and last.get("type") == env.ActionType.PASS_QIANGJIN.value
            and (last.get("metadata") or {}).get("declined") == "SANJINDAO"
        )
        if not declined_sanjindao and _opening_sanjindao_check(state, dealer):
            special = current_player_special_actions(adapter, state)
            if special:
                return ActionReport(special)
        return ActionReport(tuple(
            env.Action(dealer, env.ActionType.DISCARD, tile=tile)
            for tile in sorted(set(state.hands[dealer]))
        ))

    # Claims on the dealer's first discard are handled by normal AFTER_DISCARD
    # legality. PASS reaches NEED_DRAW; only the actual first DRAW opens this
    # Qiangjin priority check.
    if not first.get("nondealer_first_draw_done"):
        return None
    if state.phase != "AFTER_DRAW" or state.current_player != nondealer:
        return None

    last = state.last_action
    fresh_draw = (
        isinstance(last, dict)
        and last.get("type") == env.ActionType.DRAW.value
        and last.get("player") == nondealer
    )
    if fresh_draw:
        # Same-node Eight-Flower/Sanjindao outrank Qiangjin. If passed, the next
        # report falls through to the Qiangjin seat-priority chain below.
        if (_just_completed_eight_flowers(state, nondealer)
                or _just_received_third_gold(state, nondealer)
                or _later_sanjindao_draw_check(state, nondealer)):
            special = current_player_special_actions(adapter, state)
            if special:
                return ActionReport(special)

    if (not first["qiangjin_resolved"][nondealer]
            and first["qiangjin_eligible"][nondealer]):
        return ActionReport(_first_round_qiangjin_actions(state, nondealer))
    if (not first["qiangjin_resolved"][dealer]
            and first["qiangjin_eligible"][dealer]):
        return ActionReport(_first_round_qiangjin_actions(state, dealer))
    return None


def _single_youjin_offer_actions(adapter, state):
    """Known optional single-Youjin declarations after the current special window."""
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
    # actions while first-round Qiangjin stays on the staged confirmed path.
    if adapter.rules.config.simulation_only_normal_hand:
        result = _strip_unrobbable_kong_unknown(
            adapter, state, base_report(adapter, state)
        )
        if not adapter.rules.config.simulation_enable_youjin:
            return result
        if (state.special_states != ["NORMAL", "NORMAL"]
                or state.phase.startswith("YOUJIN_")):
            return result
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

    first_round = _first_round_report(adapter, state)
    if first_round is not None:
        return first_round

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
        special = current_player_special_actions(adapter, state)
        if special:
            return ActionReport(special)
        return base_report(adapter, state)
    # Mid-hand special windows no longer include Qiangjin. Sanjindao repeated
    # own-draw and Eight-Flower remain independently eligible after real draws.
    if state.phase == "AFTER_DRAW" and _last_effective_draw(state, p) is not None and (
            _just_received_third_gold(state, p)
            or _later_sanjindao_draw_check(state, p)
            or _just_completed_eight_flowers(state, p)):
        validate(adapter, state)
        special = current_player_special_actions(adapter, state)
        if special:
            return ActionReport(special)
    result = base_report(adapter, state)
    result = _strip_unrobbable_kong_unknown(adapter, state, result)
    return result
