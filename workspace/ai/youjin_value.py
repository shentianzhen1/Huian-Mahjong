"""Narrow public-information value index for confirmed single-Youjin entry.

This module deliberately does not claim full EV. It values the confirmed
single-Youjin settlement available now and the gross score of direct one-draw
upgrades to Double-You. It does not estimate the opponent's interception
chance, the opponent response draw/discard changing live counts, flower
replacement, Kong detours, or competing ordinary-Hu choices.
"""
from dataclasses import dataclass

from huian import HuianRules
from huian._legacy import env
from huian.rules.config import UnknownRuleError


@dataclass(frozen=True)
class YoujinDirectValueIndex:
    entry_discard: str
    fan: int
    single_you_points: int
    direct_upgrade_live_copies: int
    direct_upgrade_types: int
    direct_upgrade_weighted_increment: int
    mean_double_you_points_if_direct_upgrade: float | None
    current_dealer_base: int

    @property
    def is_full_ev(self):
        return False

    @property
    def coverage(self):
        return "direct_one_draw_upgrade_only"


def _coerce_melds(melds):
    result = []
    for meld in melds:
        if hasattr(meld, "kind") and hasattr(meld, "tiles"):
            result.append(meld)
            continue
        if (isinstance(meld, tuple) and len(meld) == 2
                and isinstance(meld[0], str)):
            kind, tiles = meld
            result.append(env.Meld(kind, list(tiles), None))
            continue
        raise ValueError("melds must contain Meld objects or (kind, tiles) pairs")
    return tuple(result)


def _public_base_tiles(observation):
    tiles = []
    for river in observation.discards:
        tiles.extend(tile for tile in river if tile in env.BASE_TILES)
    for seat_melds in observation.melds:
        for _, meld_tiles in seat_melds:
            tiles.extend(tile for tile in meld_tiles if tile in env.BASE_TILES)
    return tuple(tiles)


def evaluate_youjin_direct_value(
        observation, entry_discard, *, current_dealer_base=None, rules=None):
    """Return a conservative-scope, optimistic gross-value index.

    The candidate must be an actually confirmed single-Youjin entry discard
    under the current Rules implementation. The current stage uses the
    confirmed x4 settlement. Direct continuation draws are counted only when
    can_youjin_upgrade_after_draw says a Jin can immediately be discarded to
    enter Double-You; those outcomes use x8.

    The result is intentionally not probability-weighted EV. In particular,
    it does not model the opponent's preceding one-draw interception window or
    flower/Kong continuation branches.
    """
    if observation.gold_tile is None:
        raise ValueError("Youjin value requires an opened gold tile")
    if entry_discard not in observation.hand:
        raise ValueError("entry_discard must be in the acting hand")
    if current_dealer_base is None:
        if observation.match_context is None:
            raise ValueError("current_dealer_base or match context is required")
        current_dealer_base = observation.match_context.current_dealer_base
    if type(current_dealer_base) is not int or current_dealer_base < 0:
        raise ValueError("current_dealer_base must be a nonnegative integer")

    rules = HuianRules() if rules is None else rules
    open_melds = len(observation.melds[observation.seat])
    if entry_discard not in rules.youjin_entry_discards(
            observation.hand, observation.gold_tile, open_melds):
        raise ValueError("entry_discard is not a confirmed single-Youjin entry")

    melds = _coerce_melds(observation.melds[observation.seat])
    flowers = tuple(observation.flowers[observation.seat])
    after = list(observation.hand)
    after.remove(entry_discard)

    fan_result = rules.aggregate_youjin_fan(
        after, melds=melds, flowers=flowers, gold_tile=observation.gold_tile)
    if not fan_result.complete:
        raise UnknownRuleError(*fan_result.unresolved)

    single_points = (current_dealer_base + fan_result.fan) * 4
    public = list(_public_base_tiles(observation))
    public.append(entry_discard)

    live = 0
    types = 0
    weighted_increment = 0
    weighted_double_points = 0

    for draw in env.BASE_TILES:
        capacity = 3 if draw == observation.gold_tile else 4
        remaining = capacity - after.count(draw) - public.count(draw)
        if remaining <= 0:
            continue

        drawn = [*after, draw]
        if not rules.can_youjin_upgrade_after_draw(
                drawn, observation.gold_tile, open_melds):
            continue

        # Choosing the confirmed upgrade discards one Jin before Double-You.
        upgraded = list(drawn)
        upgraded.remove(observation.gold_tile)
        upgrade_fan = rules.aggregate_youjin_fan(
            upgraded, melds=melds, flowers=flowers,
            gold_tile=observation.gold_tile)
        if not upgrade_fan.complete:
            raise UnknownRuleError(*upgrade_fan.unresolved)

        double_points = (current_dealer_base + upgrade_fan.fan) * 8
        live += remaining
        types += 1
        weighted_increment += remaining * (double_points - single_points)
        weighted_double_points += remaining * double_points

    return YoujinDirectValueIndex(
        entry_discard=entry_discard,
        fan=fan_result.fan,
        single_you_points=single_points,
        direct_upgrade_live_copies=live,
        direct_upgrade_types=types,
        direct_upgrade_weighted_increment=weighted_increment,
        mean_double_you_points_if_direct_upgrade=(
            weighted_double_points / live if live else None
        ),
        current_dealer_base=current_dealer_base,
    )
