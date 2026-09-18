"""Deterministic evidence snapshots for rule-UNKNOWN simulator stops.

These snapshots do not resolve any rule. They preserve the exact simulated
position that triggered a stop so a player/replay can answer the missing rule
without having to reproduce the case manually.
"""
from copy import deepcopy

from huian.rules.context import HuContext, WinSource


def _meld_record(meld):
    return {
        "kind": meld.kind,
        "tiles": list(meld.tiles),
        "from_player": meld.from_player,
    }


def _fan_component_record(component):
    return {
        "category": component.category,
        "fan": component.fan,
        "detail": component.detail,
        "status": component.status.value,
        "evidence": component.evidence,
    }


def _ordinary_hu_audit(game, state):
    pending = state.pending_hu
    if not isinstance(pending, dict):
        return None
    try:
        source = WinSource(pending.get("source"))
    except (TypeError, ValueError):
        return None
    if source not in (WinSource.DISCARD, WinSource.SELF_DRAW):
        return None

    winner = pending["winner"]
    winning_tile = pending["winning_tile"]
    hand = list(state.hands[winner])
    if source == WinSource.DISCARD:
        hand.append(winning_tile)
    context = HuContext(source, winning_tile=winning_tile)
    rules = game.rules.rules

    audit = {
        "winner": winner,
        "source": source.value,
        "winning_tile": winning_tile,
        "hand_for_analysis": list(hand),
        "gold_count": hand.count(state.gold_tile) if state.gold_tile else 0,
    }
    try:
        hu_result = rules.analyze_hu(
            hand,
            state.gold_tile,
            open_melds=len(state.melds[winner]),
            win_context=context,
        )
    except Exception as exc:
        # Evidence collection must never convert a rule stop into a simulator
        # crash. Keep the exact exception class/message as diagnostic metadata.
        audit["analysis_error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }
        return audit

    audit["legal"] = hu_result.legal
    audit["decomposition_count"] = len(hu_result.decompositions)
    audit["may_be_truncated"] = hu_result.may_be_truncated
    audit["decompositions"] = [
        {
            "pair": list(item.pair),
            "groups": [list(group) for group in item.groups],
            "gold_used": item.gold_used,
        }
        for item in hu_result.decompositions
    ]
    if not hu_result.legal:
        return audit

    try:
        fan_result = rules.aggregate_fan(
            hand,
            state.melds[winner],
            state.flowers[winner],
            state.gold_tile,
            hu_result=hu_result,
        )
    except Exception as exc:
        audit["fan_error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }
        return audit

    audit["fan"] = {
        "complete": fan_result.complete,
        "fan": fan_result.fan,
        "accounted_fan": fan_result.accounted_fan,
        "candidate_fans": list(fan_result.candidate_fans),
        "decomposition_fans": list(fan_result.decomposition_fans),
        "unresolved": list(fan_result.unresolved),
        "components": [
            _fan_component_record(component)
            for component in fan_result.components
        ],
    }
    return audit


def build_unknown_evidence(game, rule_ids):
    """Return a JSON-friendly, deterministic snapshot for an UNKNOWN stop."""
    state = game.state
    rule_ids = tuple(dict.fromkeys(rule_ids))
    evidence = {
        "rule_ids": list(rule_ids),
        "state_hash": state.state_hash(),
        "phase": state.phase,
        "dealer": state.dealer,
        "current_player": state.current_player,
        "turn_index": state.turn_index,
        "gold_tile": state.gold_tile,
        "wall_remaining": state.wall_remaining(),
        "hands": [list(hand) for hand in state.hands],
        "flowers": [list(flowers) for flowers in state.flowers],
        "melds": [
            [_meld_record(meld) for meld in melds]
            for melds in state.melds
        ],
        "discards": [list(river) for river in state.discards],
        "special_states": list(state.special_states),
        "pending_discard": deepcopy(state.pending_discard),
        "pending_hu": deepcopy(state.pending_hu),
        "pending_kong": deepcopy(state.pending_kong),
        "last_action": deepcopy(state.last_action),
    }

    completed_kongs = []
    for player, melds in enumerate(state.melds):
        for index, meld in enumerate(melds):
            if meld.kind in ("MING_GANG", "AN_GANG", "ADDED_GANG"):
                completed_kongs.append({
                    "player": player,
                    "meld_index": index,
                    **_meld_record(meld),
                })
    if completed_kongs:
        evidence["completed_kongs"] = completed_kongs

    if state.phase == "AFTER_DISCARD" and isinstance(state.pending_discard, dict):
        player = state.current_player
        evidence["discard_hu_candidate"] = {
            "player": player,
            "discard_player": state.pending_discard["player"],
            "tile": state.pending_discard["tile"],
            "hand_before_claim": list(state.hands[player]),
            "gold_count": (
                state.hands[player].count(state.gold_tile)
                if state.gold_tile else 0
            ),
        }

    ordinary = _ordinary_hu_audit(game, state)
    if ordinary is not None:
        evidence["ordinary_hu_audit"] = ordinary

    return evidence


def summarize_match_rule_gaps(results, *, max_examples_per_rule=2):
    """Aggregate stopped match results into a compact evidence-backed rule queue."""
    if type(max_examples_per_rule) is not int or max_examples_per_rule < 0:
        raise ValueError("max_examples_per_rule must be a nonnegative integer")
    results = tuple(results)
    summary = {
        "total_matches": len(results),
        "complete_matches": 0,
        "stopped_unknown": 0,
        "rules": {},
    }
    for result in results:
        if getattr(result, "complete", False):
            summary["complete_matches"] += 1
            continue
        if getattr(result, "status", None) != "STOPPED_UNKNOWN":
            continue
        summary["stopped_unknown"] += 1
        evidence = deepcopy(getattr(result, "stopped_evidence", None))
        for rule_id in getattr(result, "unresolved", ()):
            bucket = summary["rules"].setdefault(rule_id, {
                "count": 0,
                "examples": [],
            })
            bucket["count"] += 1
            if evidence is not None and len(bucket["examples"]) < max_examples_per_rule:
                bucket["examples"].append(deepcopy(evidence))
    summary["rules"] = dict(sorted(
        summary["rules"].items(),
        key=lambda item: (-item[1]["count"], item[0]),
    ))
    return summary
