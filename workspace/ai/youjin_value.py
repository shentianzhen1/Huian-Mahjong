"""Confirmed immediate Youjin-family score value for AI research.

This is intentionally narrower than full EV.  It values only the confirmed
special path that starts by declaring single-Youjin now, then follows the
known response/progression sequence.  Opponent interception is not estimated,
so callers must treat the result as an optimistic gross-value index, not EV.
"""
from dataclasses import dataclass

from huian import HuianRules
from huian._legacy import env




@dataclass(frozen=True)
class YoujinImmediateValue:
    entry_discard: str
    fan: int
    single_you_points: int
    continuation_live_copies: int
    continuation_weighted_points: int
    gross_weighted_points: int
    current_dealer_base: int

    @property
    def is_full_ev(self):
        return False


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


def evaluate_immediate_youjin_value(
        observation, entry_discard, *, current_dealer_base=None, rules=None):
    """Return an optimistic confirmed-score index for declaring Youjin now.

    The candidate must itself be a confirmed single-Youjin entry discard.
    The base value is the current-stage x4 settlement.  Publicly-live
    continuation draws are then enumerated only to identify confirmed upgrade
    opportunities.  This function does not model the opponent's one-draw
    interception probability, so it is not a promotion-ready EV model.
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
    melds = _coerce_melds(observation.melds[observation.seat])
    flowers = tuple(observation.flowers[observation.seat])
    after = list(observation.hand)
    after.remove(entry_discard)
    if not rules.is_youjin_ready_hand(
            after, observation.gold_tile, open_melds=len(melds)):
        raise ValueError("entry_discard does not create confirmed Youjin-ready shape")

    fan_result = rules.aggregate_youjin_fan(
        after, melds=melds, flowers=flowers, gold_tile=observation.gold_tile)
    if not fan_result.complete:
        from huian.rules.config import UnknownRuleError
        raise UnknownRuleError(*fan_result.unresolved)

    single_points = (current_dealer_base + fan_result.fan) * 4
    public = []
    for river in observation.discards:
        public.extend(tile for tile in river if tile in env.BASE_TILES)
    for seat_melds in observation.melds:
        for _, meld_tiles in seat_melds:
            public.extend(tile for tile in meld_tiles if tile in env.BASE_TILES)
    public.append(entry_discard)
    own = list(after)

    live = 0
    weighted = 0
    for draw in env.BASE_TILES:
        capacity = 3 if draw == observation.gold_tile else 4
        remaining = capacity - own.count(draw) - public.count(draw)
        if remaining <= 0:
            continue
        drawn = [*after, draw]
        # Confirmed upgrade availability: after the continuation draw, a Jin
        # discard can restore the Youjin-ready structural shape.
        if observation.gold_tile not in drawn:
            continue
        upgraded = list(drawn)
        upgraded.remove(observation.gold_tile)
        if not rules.is_youjin_ready_hand(
                upgraded, observation.gold_tile, open_melds=len(melds)):
            continue
        upgrade_fan = rules.aggregate_youjin_fan(
            upgraded, melds=melds, flowers=flowers,
            gold_tile=observation.gold_tile)
        if not upgrade_fan.complete:
            from huian.rules.config import UnknownRuleError
            raise UnknownRuleError(*upgrade_fan.unresolved)
        live += remaining
        weighted += remaining * (
            (current_dealer_base + upgrade_fan.fan) * 8 - single_points)

    return YoujinImmediateValue(
        entry_discard=entry_discard,
        fan=fan_result.fan,
        single_you_points=single_points,
        continuation_live_copies=live,
        continuation_weighted_points=weighted,
        gross_weighted_points=single_points + weighted,
        current_dealer_base=current_dealer_base,
    )
