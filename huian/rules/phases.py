"""M2 legality and validation. Unknown alternatives are reported explicitly."""
from collections import Counter
from dataclasses import dataclass
from huian._legacy import env
from .config import UnknownRuleError
from .context import (DrawSource, HuContext, WinSource, YoujinStage,
                      youjin_progression_rule)
from .engine import nonnegative_int
from .special_phase_validation import (
    _active_youjin_players,
    _validate_added_kong_phase,
    _validate_pending_hu,
    _validate_pending_kong,
    _validate_youjin_response_phase,
)


@dataclass(frozen=True)
class ActionReport:
    known_actions: tuple
    unresolved: tuple[str, ...] = ()

    @property
    def complete(self):
        return not self.unresolved


PHASES = {"READY", "NEED_DRAW", "AFTER_DRAW", "AFTER_DISCARD", "AFTER_CHI",
          "AFTER_PENG", "AFTER_MING_GANG", "AFTER_AN_GANG", "NEED_FLOWER_REPLACE",
          "OPENING_QIANGJIN_CHECK", "HU_DECLARED", "TERMINAL", "ROB_KONG_WINDOW",
          "ROB_KONG_HU_DECLARED", "AFTER_ADDED_GANG", "QIANGJIN_DECLARED",
          "SANJINDAO_DECLARED", "EIGHT_FLOWER_YOU_DECLARED",
          "YOUJIN_RESPONSE_DRAW", "YOUJIN_RESPONSE_AFTER_DRAW",
          "YOUJIN_STAGE_SUCCESS", "YOUJIN_KONG_CHOICE",
          "YOUJIN_KONG_AFTER_DRAW", "YOUJIN_UPGRADE_CHOICE",
          "YOUJIN_SETTLEMENT_READY"}


def validate(adapter, state):
    # Legacy validation disallows flowers in hands. Allow only the explicit,
    # blocked replacement phase, without losing physical accounting below.
    from copy import deepcopy
    normal = deepcopy(state)
    if state.phase == "NEED_FLOWER_REPLACE" or state.terminal_reason == "WALL_16":
        normal.hands = [[t for t in hand if t not in env.FLOWERS] for hand in state.hands]
    adapter._validate_legacy_state(normal)
    if state.phase not in PHASES:
        raise ValueError("Invalid Huian phase")
    if type(state.terminal) is not bool or state.terminal != (state.phase == "TERMINAL"):
        raise ValueError("Terminal flag and phase disagree")
    if not state.terminal and len(state.wall) < adapter.rules.DRAW_WALL_REMAINING:
        raise ValueError("Active wall cannot be below the 16-tile draw boundary")
    scored_reason = isinstance(state.terminal_reason, str) and state.terminal_reason in (
        "OBSERVED_PINGHU", "OBSERVED_ZIMO", "AUTO_PINGHU", "AUTO_ZIMO",
        "SIMULATION_PINGHU", "SIMULATION_ZIMO", "PROJECT_EIGHT_FLOWER_YOU",
        "AUTO_YOUJIN", "AUTO_DOUBLE_YOU", "AUTO_TRIPLE_YOU",
        "OBSERVED_SPECIAL"
    )
    if state.terminal_reason not in (None, "WALL_16") and not scored_reason:
        raise ValueError("Invalid terminal reason")
    if (state.terminal_reason in ("SIMULATION_PINGHU", "SIMULATION_ZIMO")
            and not adapter.rules.config.simulation_only_normal_hand):
        raise ValueError("Simulation rewards cannot be imported as real outcomes")
    if state.phase == "OPENING_QIANGJIN_CHECK" and state.terminal_reason is not None:
        raise ValueError("Opening check cannot have a terminal reason")
    if state.terminal_reason == "WALL_16" and (
        not state.terminal or len(state.wall) != 16 or state.rewards != [0, 0]
    ):
        raise ValueError("Wall draw requires terminal state, 16 tiles and zero rewards")
    if scored_reason and (not state.terminal or state.rewards == [0, 0]):
        raise ValueError("Scored win requires a terminal non-zero settlement")
    for value in (state.players, state.dealer, state.current_player, state.turn_index):
        nonnegative_int(value, "state integer")
    known_special_states = {stage.value for stage in YoujinStage}
    if len(state.special_states) != 2 or any(
            s != "UNKNOWN" and s not in known_special_states
            for s in state.special_states):
        raise ValueError("Invalid special states")
    if any(type(r) is not int for r in state.rewards):
        raise ValueError("Rewards must be integer net scores")
    if not state.terminal and state.rewards != [0, 0]:
        raise ValueError("Nonterminal rewards must be zero")
    if Counter(state.physical_tiles()) != Counter(env.full_wall()):
        raise ValueError("Every physical tile must be accounted for: exactly the 144-tile set")
    _validate_pending_kong(state)
    _validate_youjin_response_phase(adapter, state)
    if state.phase == "READY":
        if (len(state.wall) != 144 or state.gold_tile is not None
                or state.pending_discard is not None or state.pending_hu is not None):
            raise ValueError("READY must be an undealt 144-tile wall")
        return
    if state.gold_tile is None:
        raise ValueError("An imported active scenario must specify its gold tile")

    # The opened gold indicator is one physical copy kept outside the drawable
    # wall. Therefore at most three copies of the gold tile may exist in
    # playable zones (wall / hands / rivers / melds). With exact 144-tile
    # conservation above, at least one copy must consequently be reserved.
    playable_gold = state.wall.count(state.gold_tile)
    playable_gold += sum(hand.count(state.gold_tile) for hand in state.hands)
    playable_gold += sum(river.count(state.gold_tile) for river in state.discards)
    playable_gold += sum(
        meld.tiles.count(state.gold_tile)
        for melds in state.melds for meld in melds
    )
    if playable_gold > 3:
        raise ValueError(
            "Opened gold indicator is non-drawable; at most three playable gold copies"
        )
    if state.reserved_tiles.count(state.gold_tile) < 1:
        raise ValueError("Active state must account for the opened gold indicator")

    for p, melds in enumerate(state.melds):
        if len(melds) > 5:
            raise ValueError("At most five melds")
        for meld in melds:
            expected_source = None if meld.kind == "AN_GANG" else 1 - p
            if meld.from_player != expected_source or (
                expected_source is not None and type(meld.from_player) is not int
            ):
                raise ValueError("Invalid meld source player")
    _validate_pending_hu(state)
    if not state.terminal:
        for p in range(2):
            expected = 16 - 3 * len(state.melds[p])
            if p == state.current_player and state.phase in (
                "AFTER_DRAW", "AFTER_CHI", "AFTER_PENG", "NEED_FLOWER_REPLACE",
                "OPENING_QIANGJIN_CHECK", "YOUJIN_RESPONSE_AFTER_DRAW",
                "YOUJIN_KONG_CHOICE", "YOUJIN_KONG_AFTER_DRAW",
                "YOUJIN_UPGRADE_CHOICE"
            ):
                expected += 1
            if (state.phase == "YOUJIN_SETTLEMENT_READY"
                    and p == state.current_player
                    and state.special_states[p] in (
                        YoujinStage.YOUJIN.value,
                        YoujinStage.DOUBLE_YOU.value)):
                # Single/Double settles only after the Youjin player's extra draw.
                expected += 1
            if (p == state.current_player and state.phase == "HU_DECLARED"
                    and state.pending_hu["source"] != WinSource.DISCARD.value):
                expected += 1
            if p == state.current_player and state.phase in (
                    "QIANGJIN_DECLARED", "SANJINDAO_DECLARED",
                    "EIGHT_FLOWER_YOU_DECLARED"):
                if len(state.hands[p]) not in (expected, expected + 1):
                    raise ValueError(f"Invalid hand size for player {p} in {state.phase}")
                continue
            if (state.phase in ("ROB_KONG_WINDOW", "ROB_KONG_HU_DECLARED")
                    and p == state.pending_kong["kong_player"]):
                expected += 1
            if len(state.hands[p]) != expected:
                raise ValueError(f"Invalid hand size for player {p} in {state.phase}")
    if state.phase.startswith("AFTER_") and state.phase.removeprefix("AFTER_") in (
        "CHI", "PENG", "MING_GANG", "AN_GANG"
    ):
        melds = state.melds[state.current_player]
        if not melds or melds[-1].kind != state.phase.removeprefix("AFTER_"):
            raise ValueError("Phase and latest meld disagree")
    if state.phase == "AFTER_ADDED_GANG":
        _validate_added_kong_phase(state)
    pending = state.pending_discard
    if state.phase == "AFTER_DISCARD":
        source = 1 - state.current_player
        if not isinstance(pending, dict) or set(pending) != {"player", "tile", "river_index"}:
            raise ValueError("Missing pending discard reference")
        index = pending["river_index"]
        if type(pending["player"]) is not int or type(index) is not int:
            raise ValueError("Invalid pending discard reference types")
        river = state.discards[source]
        if pending["player"] != source or index != len(river) - 1 or not river:
            raise ValueError("Pending discard must refer to the opponent's latest river tile")
        if river[index] != pending["tile"]:
            raise ValueError("Pending discard tile mismatch")
    elif pending is not None:
        raise ValueError("Pending discard outside claim phase")
    if state.phase == "OPENING_QIANGJIN_CHECK":
        return ActionReport((), ("qiangjin_hand_shape", "qiangjin_seat_priority", "qiangjin_settlement"))
    if state.phase == "NEED_FLOWER_REPLACE":
        if not any(t in env.FLOWERS for t in state.hands[state.current_player]):
            raise ValueError("Replacement phase without a flower")
        if any(t in env.FLOWERS for t in state.hands[1 - state.current_player]):
            raise ValueError("Flower in inactive player's hand")


def report(adapter, state):
    validate(adapter, state)
    if state.terminal:
        return ActionReport(())
    if state.phase == "READY":
        return ActionReport((), ("deal_replacement_order", "open_gold_procedure", "tianhu"))
    if state.phase == "OPENING_QIANGJIN_CHECK":
        return ActionReport((), ("qiangjin_hand_shape", "qiangjin_seat_priority", "qiangjin_settlement"))
    if state.phase == "ROB_KONG_HU_DECLARED":
        return ActionReport((), ("ROB_KONG_SCORING_UNKNOWN",))
    if state.phase == "QIANGJIN_DECLARED":
        return ActionReport((), ("qiangjin_settlement",))
    if state.phase == "SANJINDAO_DECLARED":
        return ActionReport((), ("sanjindao_settlement",))
    if state.phase == "EIGHT_FLOWER_YOU_DECLARED":
        return ActionReport((), ("eight_flower_settlement_pending",))
    if state.phase == "NEED_FLOWER_REPLACE":
        return ActionReport((), ("deal_replacement_order",))
    if state.phase == "HU_DECLARED":
        if state.pending_hu["source"] == WinSource.KONG_TAIL_DRAW.value:
            return ActionReport((), ("GANG_HU_SCORING_UNKNOWN",))
        return ActionReport((), ("win_declaration_and_settlement",))
    if state.phase == "YOUJIN_RESPONSE_DRAW":
        p = state.current_player
        return ActionReport((env.Action(
            p, env.ActionType.DRAW,
            metadata={"source": DrawSource.WALL_HEAD.value},
        ),))
    if state.phase == "YOUJIN_RESPONSE_AFTER_DRAW":
        p = state.current_player
        last = state.last_action
        try:
            draw_context = HuContext.from_draw_metadata(last.get("metadata", {}))
        except (AttributeError, ValueError):
            raise ValueError("Youjin response draw must retain auditable draw metadata")
        eligible = adapter.rules.can_win(
            state.hands[p], state.gold_tile, len(state.melds[p]),
            win_context=draw_context)
        stage = next(
            YoujinStage(value) for value in state.special_states
            if value in (
                YoujinStage.YOUJIN.value,
                YoujinStage.DOUBLE_YOU.value,
                YoujinStage.TRIPLE_YOU.value,
            )
        )
        discards = tuple(
            env.Action(
                p, env.ActionType.DISCARD, tile=tile,
                metadata={
                    "youjin_response_discard": True,
                    "stage": stage.value,
                    "declined_self_hu": bool(eligible),
                },
            )
            for tile in sorted(set(state.hands[p]))
        )
        if eligible:
            hu = env.Action(
                p, env.ActionType.HU, tile=draw_context.winning_tile,
                metadata={
                    "win_source": draw_context.source.value,
                    "kong_kind": (draw_context.kong_kind.value
                                  if draw_context.kong_kind else None),
                    "youjin_interception": True,
                    "optional": True,
                },
            )
            return ActionReport((hu, *discards))
        return ActionReport(discards)
    if state.phase == "YOUJIN_STAGE_SUCCESS":
        p = state.current_player
        stage = YoujinStage(state.special_states[p])
        progression = youjin_progression_rule(stage)
        if progression.youjin_player_draw_chances == 0:
            raise ValueError(
                "Triple-You response discard must advance directly to settlement"
            )
        return ActionReport((env.Action(
            p, env.ActionType.DRAW,
            metadata={"source": DrawSource.WALL_HEAD.value,
                      "youjin_progression": stage.value},
        ),))
    if state.phase == "YOUJIN_KONG_CHOICE":
        p = state.current_player
        hand = state.hands[p]
        actions = []
        for tile in adapter.rules.concealed_kongs(hand, state.gold_tile):
            actions.append(env.Action(
                p, env.ActionType.AN_GANG, tile=tile, tiles=(tile,) * 4,
                metadata={"youjin_kong": True},
            ))
        if adapter.rules.config.enable_added_kong:
            actions.extend(
                env.Action(
                    p, env.ActionType.ADD_KONG, tile=tile, tiles=(tile,) * 4,
                    metadata={"meld_index": index, "youjin_kong": True},
                )
                for index, tile in adapter.rules.added_kong_options(
                    hand, state.melds[p], state.gold_tile
                )
            )
        actions.append(env.Action(
            p, env.ActionType.PASS,
            metadata={
                "youjin_kong_decline": True,
                "stage": state.special_states[p],
            },
        ))
        return ActionReport(tuple(actions))

    if state.phase == "YOUJIN_KONG_AFTER_DRAW":
        p = state.current_player
        hand = state.hands[p]
        stage = YoujinStage(state.special_states[p])
        progression = youjin_progression_rule(stage)
        last = state.last_action
        draw_context = HuContext.from_draw_metadata(last.get("metadata", {}))
        actions = []
        eligible_hu = adapter.rules.can_youjin_kong_tail_ordinary_hu(
            hand, state.gold_tile, len(state.melds[p]),
            win_context=draw_context,
        )
        if eligible_hu:
            actions.append(env.Action(
                p, env.ActionType.HU, tile=draw_context.winning_tile,
                metadata={
                    "win_source": draw_context.source.value,
                    "kong_kind": (
                        draw_context.kong_kind.value
                        if draw_context.kong_kind else None
                    ),
                    "youjin_kong_tail_hu": True,
                    "optional": True,
                },
            ))
            actions.append(env.Action(
                p, env.ActionType.PASS,
                metadata={
                    "youjin_kong_tail_settle": True,
                    "stage": stage.value,
                    "alternative_to_self_hu": True,
                },
            ))
        can_upgrade = (
            progression.next_stage is not None
            and adapter.rules.can_youjin_upgrade_after_draw(
                hand, state.gold_tile, len(state.melds[p])
            )
        )
        if can_upgrade:
            action_type = (
                env.ActionType.DOUBLE_YOU
                if progression.next_stage == YoujinStage.DOUBLE_YOU
                else env.ActionType.TRIPLE_YOU
            )
            actions.append(env.Action(
                p, action_type, tile=state.gold_tile,
                metadata={
                    "from_stage": stage.value,
                    "to_stage": progression.next_stage.value,
                    "optional": True,
                    "upgrade_rule": "free_gold_after_kong_tail_draw",
                },
            ))
        if not eligible_hu:
            actions.extend(
                env.Action(
                    p, env.ActionType.DISCARD, tile=tile,
                    metadata={
                        "youjin_kong_discard": True,
                        "stage": stage.value,
                        "declined_upgrade": bool(can_upgrade),
                    },
                )
                for tile in sorted(set(hand))
                if tile != state.gold_tile
            )
        return ActionReport(tuple(actions))

    if state.phase == "YOUJIN_UPGRADE_CHOICE":
        p = state.current_player
        stage = YoujinStage(state.special_states[p])
        progression = youjin_progression_rule(stage)
        if progression.next_stage is None:
            raise ValueError("No upgrade exists after Triple-You")
        action_type = (
            env.ActionType.DOUBLE_YOU
            if progression.next_stage == YoujinStage.DOUBLE_YOU
            else env.ActionType.TRIPLE_YOU
        )
        upgrade = env.Action(
            p, action_type, tile=state.gold_tile,
            metadata={"from_stage": stage.value,
                      "to_stage": progression.next_stage.value,
                      "optional": True,
                      "upgrade_rule": "free_gold_after_own_draw"},
        )
        decline = env.Action(
            p, env.ActionType.PASS,
            metadata={"youjin_upgrade_decline": True, "stage": stage.value},
        )
        return ActionReport((upgrade, decline))
    if state.phase == "YOUJIN_SETTLEMENT_READY":
        return ActionReport((), ("youjin_settlement_context",))

    active_youjin = _active_youjin_players(state)
    if active_youjin and state.phase == "ROB_KONG_WINDOW":
        p = state.current_player
        hand = state.hands[p]
        pending = state.pending_kong
        tile = pending["tile"]
        actions = [env.Action(p, env.ActionType.PASS)]
        context = HuContext(WinSource.ROB_KONG, winning_tile=tile)
        try:
            eligible = adapter.rules.can_win(
                [*hand, tile], state.gold_tile, len(state.melds[p]),
                win_context=context,
            )
        except UnknownRuleError as exc:
            return ActionReport(tuple(actions), exc.rule_ids)
        if eligible:
            actions.insert(0, env.Action(
                p, env.ActionType.ROB_KONG_HU, tile=tile,
                metadata={
                    "win_source": WinSource.ROB_KONG.value,
                    "kong_player": pending["kong_player"],
                    "meld_index": pending["meld_index"],
                },
            ))
        return ActionReport(tuple(actions))
    if active_youjin and state.phase in ("AFTER_AN_GANG", "AFTER_ADDED_GANG"):
        p = state.current_player
        owner = active_youjin[0]
        if p != owner:
            raise ValueError("Youjin kong completion must return to the Youjin owner")
        return ActionReport((env.Action(
            p, env.ActionType.DRAW,
            metadata={
                "source": DrawSource.WALL_TAIL.value,
                "kong_kind": state.phase.removeprefix("AFTER_"),
                "youjin_kong_tail": True,
            },
        ),))
    if state.special_states != ["NORMAL", "NORMAL"]:
        return ActionReport((), ("youjin_permissions",))
    p = state.current_player
    hand = state.hands[p]
    phase = state.phase
    A, T = env.Action, env.ActionType
    if phase == "ROB_KONG_WINDOW":
        pending = state.pending_kong
        tile = pending["tile"]
        actions = [A(p, T.PASS)]
        context = HuContext(WinSource.ROB_KONG, winning_tile=tile)
        try:
            eligible = adapter.rules.can_win(
                [*hand, tile], state.gold_tile, len(state.melds[p]), win_context=context)
        except UnknownRuleError as exc:
            return ActionReport(tuple(actions), exc.rule_ids)
        if eligible:
            actions.insert(0, A(p, T.ROB_KONG_HU, tile=tile, metadata={
                "win_source": WinSource.ROB_KONG.value,
                "kong_player": pending["kong_player"], "meld_index": pending["meld_index"],
            }))
        return ActionReport(tuple(actions))
    if adapter.rules.is_wall_draw(state):
        return ActionReport(())
    if phase in ("AFTER_MING_GANG", "AFTER_AN_GANG", "AFTER_ADDED_GANG"):
        # Importing this phase explicitly means kong response resolution is over.
        return ActionReport((A(p, T.DRAW, metadata={
            "source": DrawSource.WALL_TAIL.value,
            "kong_kind": phase.removeprefix("AFTER_"),
        }),))
    if phase == "NEED_DRAW":
        return ActionReport((A(p, T.DRAW, metadata={"source": DrawSource.WALL_HEAD.value}),))
    gold_unresolved = []
    simulation_declined_sanjindao = (
        adapter.rules.config.simulation_only_normal_hand
        and adapter.rules.can_sanjindao(hand, state.gold_tile)
    )
    if state.gold_tile in hand and not adapter.rules.config.simulation_only_normal_hand:
        gold_unresolved.append("youjin_trigger")
    if phase in ("AFTER_CHI", "AFTER_PENG"):
        if gold_unresolved:
            return ActionReport((), tuple(gold_unresolved))
        return ActionReport(tuple(A(p, T.DISCARD, tile=t) for t in sorted(set(hand))))
    if phase == "AFTER_DISCARD" and gold_unresolved:
        return ActionReport((), tuple(gold_unresolved))
    actions, unknown = [], []
    if phase == "AFTER_DRAW":
        draw_context = None
        last = state.last_action
        if (isinstance(last, dict) and last.get("type") == T.DRAW.value
                and last.get("player") == p):
            try:
                draw_context = HuContext.from_draw_metadata(last.get("metadata", {}))
            except ValueError:
                draw_context = None
        if (not simulation_declined_sanjindao
                and draw_context is not None
                and adapter.rules.can_win(
                    hand, state.gold_tile, len(state.melds[p]), win_context=draw_context)):
            metadata = {"win_source": draw_context.source.value,
                        "kong_kind": (draw_context.kong_kind.value
                                      if draw_context.kong_kind else None)}
            actions.append(A(p, T.HU, tile=draw_context.winning_tile, metadata=metadata))
            if draw_context.is_gang_hu:
                # Audit the declaration before stopping at its unknown settlement.
                return ActionReport(tuple(actions))
            unknown.extend(gold_unresolved)
            if not adapter.rules.config.simulation_only_normal_hand:
                unknown.extend(("self_draw_decline", "win_declaration_and_settlement"))
            return ActionReport(tuple(actions), tuple(unknown))
        if (not simulation_declined_sanjindao
                and draw_context is None
                and adapter.rules.can_win(
                    hand, state.gold_tile, len(state.melds[p]))):
            return ActionReport((), tuple(gold_unresolved + ["win_declaration_and_settlement"]))
        if gold_unresolved:
            return ActionReport((), tuple(gold_unresolved))
        actions.extend(A(p, T.DISCARD, tile=t) for t in sorted(set(hand)))
        kongs = adapter.rules.concealed_kongs(hand, state.gold_tile)
        if kongs:
            if adapter.rules.config.experimental_no_rob_kong:
                actions.extend(A(p, T.AN_GANG, tile=t, tiles=(t,) * 4) for t in kongs)
            else:
                unknown.append("rob_kong")
        if adapter.rules.config.enable_added_kong:
            actions.extend(A(p, T.ADD_KONG, tile=tile, tiles=(tile,) * 4,
                             metadata={"meld_index": index})
                           for index, tile in adapter.rules.added_kong_options(
                               hand, state.melds[p], state.gold_tile))
    elif phase == "AFTER_DISCARD":
        tile = state.pending_discard["tile"]
        candidates = adapter.rules.meld_options(hand, tile, state.gold_tile)
        actions.extend(A(p, T.CHI, tile=tile, tiles=seq) for seq in candidates["chi"])
        if candidates["peng"]:
            actions.append(A(p, T.PENG, tile=tile, tiles=(tile,) * 3))
        if candidates["ming_gang"]:
            if adapter.rules.config.experimental_no_rob_kong:
                actions.append(A(p, T.MING_GANG, tile=tile, tiles=(tile,) * 4))
            else:
                unknown.append("rob_kong")
        if (not simulation_declined_sanjindao
                and adapter.rules.can_win(
                    hand + [tile], state.gold_tile, len(state.melds[p]),
                    "pinghu", winning_tile=tile)):
            context = HuContext(WinSource.DISCARD, tile)
            actions.append(A(p, T.HU, tile=tile, metadata={
                "win_source": context.source.value, "kong_kind": None,
            }))
            if not adapter.rules.config.simulation_only_normal_hand:
                unknown.append("win_declaration_and_settlement")
        actions.append(A(p, T.PASS))
    return ActionReport(tuple(actions), tuple(unknown))


def authorize(adapter, state, action):
    result = report(adapter, state)
    if type(action.player) is not int:
        raise ValueError("Invalid action player")
    if action.type in (env.ActionType.ADD_KONG, env.ActionType.ROB_KONG_HU):
        if (not isinstance(action.metadata, dict)
                or type(action.metadata.get("meld_index")) is not int):
            raise ValueError("A kong action requires an integer meld index")
        if (action.type == env.ActionType.ROB_KONG_HU
                and type(action.metadata.get("kong_player")) is not int):
            raise ValueError("A rob-kong action requires an integer kong player")
    # Individually known actions can execute even when other alternatives are
    # unresolved. legal_actions() never presents this as a complete action set.
    if action in result.known_actions:
        return
    if result.unresolved:
        raise UnknownRuleError(*result.unresolved)
    raise ValueError(f"Illegal action: {action}")
