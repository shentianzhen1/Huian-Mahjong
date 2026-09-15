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
          "OPENING_QIANGJIN_CHECK", "HU_DECLARED", "TERMINAL"}


def _validate_pending_hu(state):
    pending = state.pending_hu
    if state.phase != "HU_DECLARED":
        if pending is not None:
            raise ValueError("Pending Hu outside HU_DECLARED")
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
    observed_reason = isinstance(state.terminal_reason, str) and state.terminal_reason in (
        "OBSERVED_PINGHU", "OBSERVED_ZIMO", "SIMULATION_PINGHU", "SIMULATION_ZIMO"
    )
    if state.terminal_reason not in (None, "WALL_16") and not observed_reason:
        raise ValueError("Invalid terminal reason")
    if state.phase == "OPENING_QIANGJIN_CHECK" and state.terminal_reason is not None:
        raise ValueError("Opening check cannot have a terminal reason")
    if state.terminal_reason == "WALL_16" and (
        not state.terminal or len(state.wall) != 16 or state.rewards != [0, 0]
    ):
        raise ValueError("Wall draw requires terminal state, 16 tiles and zero rewards")
    if observed_reason and (not state.terminal or state.rewards == [0, 0]):
        raise ValueError("Observed win requires a terminal non-zero settlement")
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
    if state.phase == "READY":
        if (len(state.wall) != 144 or state.gold_tile is not None
                or state.pending_discard is not None or state.pending_hu is not None):
            raise ValueError("READY must be an undealt 144-tile wall")
        return
    if state.gold_tile is None:
        raise ValueError("An imported active scenario must specify its gold tile")
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
                "OPENING_QIANGJIN_CHECK"
            ):
                expected += 1
            if (p == state.current_player and state.phase == "HU_DECLARED"
                    and state.pending_hu["source"] != WinSource.DISCARD.value):
                expected += 1
            if len(state.hands[p]) != expected:
                raise ValueError(f"Invalid hand size for player {p} in {state.phase}")
    if state.phase.startswith("AFTER_") and state.phase.removeprefix("AFTER_") in (
        "CHI", "PENG", "MING_GANG", "AN_GANG"
    ):
        melds = state.melds[state.current_player]
        if not melds or melds[-1].kind != state.phase.removeprefix("AFTER_"):
            raise ValueError("Phase and latest meld disagree")
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
    if state.phase == "NEED_FLOWER_REPLACE":
        return ActionReport((), ("deal_replacement_order",))
    if state.phase == "HU_DECLARED":
        unresolved = ["win_declaration_and_settlement"]
        if state.pending_hu["source"] == WinSource.KONG_TAIL_DRAW.value:
            unresolved.append("gang_hu_scoring")
        return ActionReport((), tuple(unresolved))
    if state.special_states != ["NORMAL", "NORMAL"]:
        return ActionReport((), ("youjin_permissions",))
    if adapter.rules.is_wall_draw(state):
        return ActionReport(())
    p = state.current_player
    hand = state.hands[p]
    phase = state.phase
    A, T = env.Action, env.ActionType
    if phase in ("AFTER_MING_GANG", "AFTER_AN_GANG"):
        # Importing this phase explicitly means kong response resolution is over.
        return ActionReport((A(p, T.DRAW, metadata={
            "source": DrawSource.WALL_TAIL.value,
            "kong_kind": phase.removeprefix("AFTER_"),
        }),))
    if phase == "NEED_DRAW":
        return ActionReport((A(p, T.DRAW, metadata={"source": DrawSource.WALL_HEAD.value}),))
    gold_unresolved = []
    if state.gold_tile in hand and not adapter.rules.config.simulation_only_normal_hand:
        gold_unresolved.append("youjin_trigger")
        if adapter.rules.can_sanjindao(hand, state.gold_tile):
            gold_unresolved.append("sanjindao_timing")
            return ActionReport((), tuple(gold_unresolved))
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
        if draw_context is not None and adapter.rules.can_win(
                hand, state.gold_tile, len(state.melds[p]), win_context=draw_context):
            metadata = {"win_source": draw_context.source.value,
                        "kong_kind": (draw_context.kong_kind.value
                                      if draw_context.kong_kind else None)}
            actions.append(A(p, T.HU, tile=draw_context.winning_tile, metadata=metadata))
            unknown.extend(gold_unresolved)
            if not adapter.rules.config.simulation_only_normal_hand:
                unknown.extend(("self_draw_decline", "win_declaration_and_settlement"))
            if draw_context.is_gang_hu:
                unknown.append("gang_hu_scoring")
            return ActionReport(tuple(actions), tuple(unknown))
        if draw_context is None and adapter.rules.can_win(
                hand, state.gold_tile, len(state.melds[p])):
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
        if any(m.kind == "PENG" and m.tiles[0] in hand for m in state.melds[p]):
            unknown.append("added_kong_details")
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
        if adapter.rules.can_win(hand + [tile], state.gold_tile, len(state.melds[p]),
                                 "pinghu", winning_tile=tile):
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
    # Individually known actions can execute even when other alternatives are
    # unresolved. legal_actions() never presents this as a complete action set.
    if action in result.known_actions:
        return
    if result.unresolved:
        raise UnknownRuleError(*result.unresolved)
    raise ValueError(f"Illegal action: {action}")
