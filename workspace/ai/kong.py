"""Public-information shadow analysis for Huian kong opportunities.

This module deliberately does not choose actions.  It projects ordinary hand
structure after each legal kong while preserving explicit blockers for
rob-kong and kong-tail settlement paths that are not yet evidence-complete.
"""
from dataclasses import dataclass

from huian._legacy import env
from huian.rules import HuianRules, KongKind

from .shanten import analyze_effective_tiles, best_discard


@dataclass(frozen=True)
class KongOpportunity:
    action_type: str
    tile: str
    phase: str
    baseline_mode: str
    baseline_discard: str | None
    baseline_shanten: int
    baseline_live_copies: int
    baseline_effective_types: int
    post_kong_shanten: int
    post_kong_live_copies: int
    post_kong_effective_types: int
    kong_fan: int
    kong_fan_status: str
    winning_tail_copies: int
    structural_relation: str
    blockers: tuple[str, ...]


def _public_tiles(observation):
    tiles = []
    for river in observation.discards:
        tiles.extend(river)
    for melds in observation.melds:
        for _, meld_tiles in melds:
            tiles.extend(meld_tiles)
    return tuple(tile for tile in tiles if tile in env.BASE_TILES)


def _offense_key(shanten, live_copies, effective_types):
    return (shanten, -live_copies, -effective_types)


def _relation(post_key, baseline_key):
    if post_key < baseline_key:
        return "BETTER"
    if post_key > baseline_key:
        return "WORSE"
    return "EQUAL"


def _remove_copies(hand, tile, count):
    result = list(hand)
    for _ in range(count):
        try:
            result.remove(tile)
        except ValueError as exc:
            raise ValueError("kong action consumes tiles absent from acting hand") from exc
    return result


def analyze_kong_actions(observation, legal_actions):
    """Return auditable structural projections for the legal kong actions.

    Inputs are restricted to ``PlayerObservation`` and the acting player's
    legal actions.  The opponent hand, wall order, and reserved tiles are never
    consulted.  Results are diagnostics, not action recommendations.
    """
    kong_types = {
        env.ActionType.MING_GANG,
        env.ActionType.AN_GANG,
        env.ActionType.ADD_KONG,
    }
    actions = sorted(
        (action for action in legal_actions if action.type in kong_types),
        key=lambda action: (action.type.value, action.tile or "", action.tiles),
    )
    if not actions:
        return ()

    public_tiles = _public_tiles(observation)
    open_melds = len(observation.melds[observation.seat])
    rules = HuianRules()
    results = []

    for action in actions:
        if action.player != observation.seat:
            raise ValueError("kong action belongs to a different player")
        tile = action.tile
        if tile not in env.BASE_TILES:
            raise ValueError("kong action requires a normal tile")

        if action.type == env.ActionType.MING_GANG:
            if observation.phase != "AFTER_DISCARD":
                raise ValueError("MING_GANG projection requires AFTER_DISCARD")
            baseline = analyze_effective_tiles(
                observation.hand,
                gold_tile=observation.gold_tile,
                open_melds=open_melds,
                visible_tiles=public_tiles,
            )
            baseline_mode = "PASS"
            baseline_discard = None
            post_hand = _remove_copies(observation.hand, tile, 3)
            post_open_melds = open_melds + 1
            public_after = (*public_tiles, tile, tile, tile)
            kind = KongKind.MING_GANG
            blockers = []
        else:
            if observation.phase != "AFTER_DRAW":
                raise ValueError(
                    f"{action.type.value} projection requires AFTER_DRAW")
            baseline = best_discard(
                observation.hand,
                gold_tile=observation.gold_tile,
                open_melds=open_melds,
                visible_tiles=public_tiles,
            )
            baseline_mode = "BEST_DISCARD"
            baseline_discard = baseline.discard
            if action.type == env.ActionType.AN_GANG:
                post_hand = _remove_copies(observation.hand, tile, 4)
                post_open_melds = open_melds + 1
                public_after = (*public_tiles, tile, tile, tile, tile)
                kind = KongKind.AN_GANG
                blockers = []
            else:
                post_hand = _remove_copies(observation.hand, tile, 1)
                post_open_melds = open_melds
                public_after = (*public_tiles, tile)
                kind = KongKind.ADDED_GANG
                blockers = ["rob_kong"]

        post = analyze_effective_tiles(
            post_hand,
            gold_tile=observation.gold_tile,
            open_melds=post_open_melds,
            visible_tiles=public_after,
        )
        winning_tail_copies = sum(
            item.remaining for item in post.effective_tiles if item.winning)
        if winning_tail_copies:
            blockers.append("gang_hu_scoring")

        fan = rules.kong_fan(kind, tile)
        baseline_types = len(baseline.effective_tiles)
        post_types = len(post.effective_tiles)
        baseline_key = _offense_key(
            baseline.shanten, baseline.total_live_copies, baseline_types)
        post_key = _offense_key(
            post.shanten, post.total_live_copies, post_types)
        results.append(KongOpportunity(
            action_type=action.type.value,
            tile=tile,
            phase=observation.phase,
            baseline_mode=baseline_mode,
            baseline_discard=baseline_discard,
            baseline_shanten=baseline.shanten,
            baseline_live_copies=baseline.total_live_copies,
            baseline_effective_types=baseline_types,
            post_kong_shanten=post.shanten,
            post_kong_live_copies=post.total_live_copies,
            post_kong_effective_types=post_types,
            kong_fan=fan.fan,
            kong_fan_status=fan.status.value,
            winning_tail_copies=winning_tail_copies,
            structural_relation=_relation(post_key, baseline_key),
            blockers=tuple(blockers),
        ))

    return tuple(results)
