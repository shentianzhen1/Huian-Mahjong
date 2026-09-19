"""Known ordinary self-draw value for score-aware AI experiments.

This module is deliberately narrower than full EV. It only values the next
base-tile draws that immediately complete a confirmed ordinary self-draw and
uses the confirmed settlement formula:

    (current dealer base + winner fan) * 2

It does not model:
- Qiangjin / Sanjindao / Youjin / Eight-Flower outcomes;
- opponent responses;
- flower replacement probability;
- multi-turn continuation value.

Callers must treat the result as an auditable score-weighted wait index, not a
complete expected-value estimate.
"""
from dataclasses import dataclass

from huian import HuianRules
from huian._legacy import env
from huian.rules.config import UnknownRuleError

from .shanten import analyze_effective_tiles


@dataclass(frozen=True)
class OrdinaryWinningDrawValue:
    tile: str
    remaining: int
    fan: int
    net_points: int


@dataclass(frozen=True)
class OrdinaryImmediateValue:
    draws: tuple[OrdinaryWinningDrawValue, ...]
    total_live_copies: int
    weighted_net_points: int
    mean_net_points_if_win: float
    current_dealer_base: int

    @property
    def winning_tile_types(self):
        return tuple(item.tile for item in self.draws)

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


def evaluate_tenpai_ordinary_value(
        hand, *, gold_tile, melds=(), flowers=(),
        current_dealer_base, visible_tiles=(), rules=None):
    """Score immediate ordinary self-draw waits for a pre-draw tenpai hand.

    The hand must be structural ordinary tenpai (shanten 0). All effective
    draws must be ordinary Hu structures. Any unresolved fan component raises
    UnknownRuleError so an AI caller can fall back to its previous policy.
    """
    if type(current_dealer_base) is not int or current_dealer_base < 0:
        raise ValueError("current_dealer_base must be a nonnegative integer")
    rules = HuianRules() if rules is None else rules
    melds = _coerce_melds(tuple(melds))
    flowers = tuple(flowers)
    analysis = analyze_effective_tiles(
        tuple(hand),
        gold_tile=gold_tile,
        open_melds=len(melds),
        visible_tiles=tuple(visible_tiles),
    )
    if analysis.shanten != 0:
        raise ValueError("ordinary immediate value requires shanten 0")

    draw_values = []
    for effective in analysis.effective_tiles:
        if not effective.winning:
            raise RuntimeError("tenpai effective draw must complete ordinary structure")
        drawn_hand = [*hand, effective.tile]
        hu_result = rules.analyze_hu(
            drawn_hand,
            gold_tile=gold_tile,
            open_melds=len(melds),
            win_type="zimo",
            winning_tile=effective.tile,
        )
        if not hu_result.legal:
            raise RuntimeError(
                f"shanten engine and Hu solver disagree on winning tile {effective.tile}"
            )
        fan_result = rules.aggregate_fan(
            drawn_hand,
            melds=melds,
            flowers=flowers,
            gold_tile=gold_tile,
            hu_result=hu_result,
        )
        if not fan_result.complete:
            raise UnknownRuleError(*fan_result.unresolved)
        net_points = (current_dealer_base + fan_result.fan) * 2
        draw_values.append(OrdinaryWinningDrawValue(
            tile=effective.tile,
            remaining=effective.remaining,
            fan=fan_result.fan,
            net_points=net_points,
        ))

    total_live = sum(item.remaining for item in draw_values)
    if total_live <= 0:
        return OrdinaryImmediateValue(
            draws=tuple(draw_values),
            total_live_copies=0,
            weighted_net_points=0,
            mean_net_points_if_win=0.0,
            current_dealer_base=current_dealer_base,
        )
    weighted = sum(item.remaining * item.net_points for item in draw_values)
    return OrdinaryImmediateValue(
        draws=tuple(draw_values),
        total_live_copies=total_live,
        weighted_net_points=weighted,
        mean_net_points_if_win=weighted / total_live,
        current_dealer_base=current_dealer_base,
    )
