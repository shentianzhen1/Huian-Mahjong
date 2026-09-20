"""M2 legality and validation. Unknown alternatives are reported explicitly."""
from collections import Counter
from dataclasses import dataclass
from huian._legacy import env
from .config import UnknownRuleError
from .context import DrawSource, HuContext, WinSource, YoujinStage
from .engine import nonnegative_int


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
          "YOUJIN_STAGE_SUCCESS", "YOUJIN_UPGRADE_CHOICE",
          "YOUJIN_SETTLEMENT_READY"}


YOUJIN_RESPONSE_PHASES = {
    "YOUJIN_RESPONSE_DRAW",
    "YOUJIN_RESPONSE_AFTER_DRAW",
    "YOUJIN_STAGE_SUCCESS",
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


def _validate_youjin_response_phase(state):
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
        if (not isinstance(last, dict)
                or last.get("type") != env.ActionType.DRAW.value
                or last.get("player") != responder):
            raise ValueError("Youjin stage success requires the completed opponent draw")
    if state.phase == "YOUJIN_UPGRADE_CHOICE":
        if state.special_states[youjin_player] == YoujinStage.TRIPLE_YOU.value:
            raise ValueError("Triple-You has no further upgrade choice")
        if not adapter.rules.can_youjin_upgrade_after_draw(
                state.hands[youjin_player], state.gold_tile,
                len(state.melds[youjin_player])):
            raise ValueError("Youjin upgrade choice requires a structurally free gold")
    if state.phase == "YOUJIN_SETTLEMENT_READY":
        # Single/Double settlement follows the Youjin player's extra draw.
        # Triple settlement follows the opponent miss directly.
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
    if (not isinstance(state.youjin_response_draws, list)
            or len(state.youjin_response_draws) != 2
            or any(type(value) is not int or value < 0
                   for value in state.youjin_response_draws)):
        raise ValueError("Youjin response draw counts must be two nonnegative integers")
    if any(type(r) is not int for r in state.rewards):
        raise ValueError("Rewards must be integer net scores")
    if not state.terminal and state.rewards != [0, 0]:
        raise ValueError("Nonterminal rewards must be zero")
    if Counter(state.physical_tiles()) != Counter(env.full_wall()):
        raise ValueError("Every physical tile must be accounted for: exactly the 144-tile set")
    _validate_pending_kong(state)
    _validate_youjin_response_phase(state)
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
            expected = (16 - 3 * len(state.melds[p])
                        + state.youjin_response_draws[p])
            if p == state.current_player and state.phase in (
                "AFTER_DRAW", "AFTER_CHI", "AFTER_PENG", "NEED_FLOWER_REPLACE",
                "OPENING_QIANGJIN_CHECK", "YOUJIN_RESPONSE_AFTER_DRAW",
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
        if adapter.rules.can_win(
                state.hands[p], state.gold_tile, len(state.melds[p]),
                win_context=draw_context):
            action = env.Action(
                p, env.ActionType.HU, tile=draw_context.winning_tile,
                metadata={"win_source": draw_context.source.value,
                          "kong_kind": (draw_context.kong_kind.value
                                        if draw_context.kong_kind else None),
                          "youjin_interception": True},
            )
            return ActionReport((action,), ("youjin_response_hu_decline",))
        return ActionReport((), ("youjin_stage_success_resolution",))
    if state.phase == "YOUJIN_STAGE_SUCCESS":
        return ActionReport((), ("youjin_stage_success_resolution",))
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
