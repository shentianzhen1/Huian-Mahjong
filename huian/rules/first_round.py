"""Player-confirmed first-round Qiangjin/Tianting analysis.

The helpers in this module never move a physical tile for Qiangjin.  They only
construct an auditable virtual 17-tile analysis hand from the opened Gold copy.
The opened indicator remains in ``reserved_tiles`` so the physical 144-tile
state and the three-playable-Gold limit stay unchanged.
"""
from huian._legacy import core
from huian._compat.qzcore.win_checker import winning_decompositions

from .config import UnknownRuleError
from .context import HuContext, WinSource
from .fan import FanAggregator
from .models import HuDecomposition, HuResult
from .registry import DEFAULT_RULE_SNAPSHOT

EVIDENCE_ID = "player_confirmed_special_rules_20261006_v1"
MAX_DECOMPOSITIONS = 64


def _rules():
    # Lazy import avoids a module cycle while environment transitions import
    # this helper. The staged confirmed flow uses the target-room defaults.
    from .engine import HuianRules
    return HuianRules()


def _virtual_hu_result(virtual_hand, gold_tile, open_melds=0):
    """Analyze a Qiangjin virtual hand without treating virtual Gold as playable.

    A dealer may physically hold all three playable Gold copies.  Virtually
    adding the reserved opened copy for Qiangjin can therefore produce four
    Gold positions in the analysis hand.  The ordinary physical-hand validator
    correctly rejects that shape for normal play, so this special analysis uses
    the same decomposition solver directly instead of weakening the global
    three-playable-copy invariant.
    """
    raw = winning_decompositions(
        list(virtual_hand), gold_tile, open_melds,
        max_solutions=MAX_DECOMPOSITIONS + 1,
    )
    truncated = len(raw) > MAX_DECOMPOSITIONS
    raw = raw[:MAX_DECOMPOSITIONS]
    decompositions = tuple(
        HuDecomposition(
            pair=tuple(split["pair"]),
            groups=tuple(tuple(group) for group in split["groups"]),
        )
        for split in raw
    )
    return HuResult(
        legal=bool(decompositions),
        decompositions=decompositions,
        gold_tile=gold_tile,
        open_melds=open_melds,
        context=HuContext(WinSource.SELF_DRAW, winning_tile=gold_tile),
        may_be_truncated=truncated,
    )


def _virtual_fan(rules, virtual_hand, melds, flowers, gold_tile, hu_result):
    if hu_result.may_be_truncated:
        raise UnknownRuleError("decomposition_scoring")
    aggregator = FanAggregator(rules)
    base, unresolved = aggregator._base_components(
        virtual_hand, tuple(melds), tuple(flowers), gold_tile
    )
    if unresolved:
        raise UnknownRuleError(*unresolved)
    candidate_fans = []
    for decomposition in hu_result.decompositions:
        components = tuple(base + aggregator._concealed_components(
            decomposition, hu_result
        ))
        candidate_fans.append(sum(component.fan for component in components))
    if not candidate_fans:
        raise ValueError("Qiangjin fan requires a legal virtual Hu")
    return max(candidate_fans), tuple(sorted(set(candidate_fans)))


def qiangjin_virtual_analysis(state, player, *, role, drawn_tile=None, rules=None):
    """Return confirmed virtual-Hu eligibility/fan for one first-round seat."""
    DEFAULT_RULE_SNAPSHOT.require_confirmed("legality.qiangjin_virtual_gold_shape")
    DEFAULT_RULE_SNAPSHOT.require_confirmed("state_machine.qiangjin_first_round_timing")
    if player not in (0, 1):
        raise ValueError("player must be seat 0 or 1")
    if role not in ("dealer_after_first_discard", "nondealer_after_first_draw"):
        raise ValueError("invalid first-round Qiangjin role")
    gold = state.gold_tile
    if gold is None or state.reserved_tiles.count(gold) < 1:
        raise ValueError("Qiangjin requires the reserved opened Gold copy")
    rules = _rules() if rules is None else rules
    hand = list(state.hands[player])
    if role == "dealer_after_first_discard":
        if player != state.dealer or len(hand) != 16:
            raise ValueError("dealer Qiangjin analysis requires remaining 16 tiles")
        virtual = [*hand, gold]
    else:
        if player == state.dealer or len(hand) != 17:
            raise ValueError("nondealer Qiangjin analysis requires first-draw 17 tiles")
        if drawn_tile not in core.BASE_TILES or drawn_tile not in hand:
            return {
                "eligible": False,
                "fan": None,
                "candidate_fans": (),
                "reason": "FIRST_DRAW_NOT_NORMAL_TILE",
            }
        virtual = list(hand)
        virtual.remove(drawn_tile)  # exactly the one first-drawn physical tile
        virtual.append(gold)        # the single reserved indicator copy, virtually
    if len(virtual) != 17 or virtual.count(gold) > 4:
        raise ValueError("Qiangjin virtual hand must be exactly 17 tiles")
    result = _virtual_hu_result(virtual, gold, len(state.melds[player]))
    if not result.legal:
        return {
            "eligible": False,
            "fan": None,
            "candidate_fans": (),
            "reason": "VIRTUAL_HAND_NOT_HU",
        }
    fan, candidates = _virtual_fan(
        rules, virtual, state.melds[player], state.flowers[player], gold, result
    )
    return {
        "eligible": True,
        "fan": fan,
        "candidate_fans": candidates,
        "reason": "CONFIRMED_VIRTUAL_GOLD_HU",
    }


def tianting_status(hand, gold_tile, *, rules=None):
    """Structural 16-tile Ting status only; it never changes fan or multiplier."""
    DEFAULT_RULE_SNAPSHOT.require_confirmed("state_machine.tianting_status")
    rules = _rules() if rules is None else rules
    if len(hand) != 16:
        raise ValueError("Tianting status requires exactly 16 concealed tiles")
    waits = rules.ting_tiles(list(hand), gold_tile)
    return bool(waits), tuple(item["tile"] for item in waits)


def new_first_round_state(state, *, current_dealer_base, rules=None):
    """Create provenance immediately after a non-terminal Gold is determined."""
    DEFAULT_RULE_SNAPSHOT.require_confirmed("state_machine.qiangjin_seat_priority")
    if type(current_dealer_base) is not int or current_dealer_base < 0:
        raise ValueError("current_dealer_base must be a nonnegative integer")
    dealer = state.dealer
    nondealer = 1 - dealer
    if len(state.hands[dealer]) != 17 or len(state.hands[nondealer]) != 16:
        raise ValueError("first round requires dealer17/nondealer16")
    listening, waits = tianting_status(
        state.hands[nondealer], state.gold_tile, rules=rules
    )
    tianting = [None, None]
    tianting_waits = [[], []]
    tianting[nondealer] = listening
    tianting_waits[nondealer] = list(waits)
    return {
        "evidence_id": EVIDENCE_ID,
        "rule_snapshot_fingerprint": DEFAULT_RULE_SNAPSHOT.fingerprint,
        "active": True,
        "dealer": dealer,
        "nondealer": nondealer,
        "current_dealer_base": current_dealer_base,
        "dealer_first_discard_done": False,
        "dealer_first_discard_tile": None,
        "nondealer_first_draw_done": False,
        "nondealer_first_draw_tile": None,
        "tianting": tianting,
        "tianting_waits": tianting_waits,
        "qiangjin_eligible": [False, False],
        "qiangjin_resolved": [False, False],
        "qiangjin_fan": [None, None],
        "qiangjin_candidate_fans": [[], []],
        "qiangjin_reason": [None, None],
    }


def record_dealer_first_discard(state, tile, *, rules=None):
    first = state.first_round
    if not isinstance(first, dict) or not first.get("active"):
        return
    dealer = state.dealer
    if first.get("dealer_first_discard_done"):
        return
    if len(state.hands[dealer]) != 16:
        raise ValueError("dealer first discard must leave 16 tiles")
    first["dealer_first_discard_done"] = True
    first["dealer_first_discard_tile"] = tile
    listening, waits = tianting_status(
        state.hands[dealer], state.gold_tile, rules=rules
    )
    first["tianting"][dealer] = listening
    first["tianting_waits"][dealer] = list(waits)
    result = qiangjin_virtual_analysis(
        state, dealer, role="dealer_after_first_discard", rules=rules
    )
    first["qiangjin_eligible"][dealer] = result["eligible"]
    first["qiangjin_resolved"][dealer] = not result["eligible"]
    first["qiangjin_fan"][dealer] = result["fan"]
    first["qiangjin_candidate_fans"][dealer] = list(result["candidate_fans"])
    first["qiangjin_reason"][dealer] = result["reason"]


def record_nondealer_first_draw(state, tile, *, rules=None):
    first = state.first_round
    if not isinstance(first, dict) or not first.get("active"):
        return
    nondealer = 1 - state.dealer
    if first.get("nondealer_first_draw_done"):
        return
    if not first.get("dealer_first_discard_done"):
        raise ValueError("nondealer first draw cannot precede dealer first discard")
    first["nondealer_first_draw_done"] = True
    first["nondealer_first_draw_tile"] = tile
    result = qiangjin_virtual_analysis(
        state, nondealer, role="nondealer_after_first_draw",
        drawn_tile=tile, rules=rules,
    )
    first["qiangjin_eligible"][nondealer] = result["eligible"]
    first["qiangjin_resolved"][nondealer] = not result["eligible"]
    first["qiangjin_fan"][nondealer] = result["fan"]
    first["qiangjin_candidate_fans"][nondealer] = list(result["candidate_fans"])
    first["qiangjin_reason"][nondealer] = result["reason"]


def cancel_first_round(state, reason):
    first = getattr(state, "first_round", None)
    if isinstance(first, dict) and first.get("active"):
        first["active"] = False
        first["closed_reason"] = str(reason)
