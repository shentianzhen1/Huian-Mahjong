"""Deterministic opening planner for the Huian online-room V0.1 profile.

The planner exposes the selected indicator position instead of deciding whether
the visible indicator is removed from the physical wall; that target-room
accounting detail still needs a direct observation.
"""
from copy import deepcopy
from dataclasses import dataclass

from huian._legacy import env
from mahjong_framework import MahjongOpeningPlugin
from .flowers import FlowerReplacementResult, replace_flowers


@dataclass(frozen=True)
class GoldIndicator:
    tile: str
    wall_index: int
    skipped_flowers: tuple[str, ...]


@dataclass(frozen=True)
class OpeningPlan:
    dealer: int
    hands: tuple[tuple[str, ...], tuple[str, ...]]
    flowers: tuple[tuple[str, ...], tuple[str, ...]]
    wall: tuple[str, ...]
    flower_replacement: FlowerReplacementResult
    gold_indicator: GoldIndicator


class HuianOpeningPlugin(MahjongOpeningPlugin):
    """Huian two-player opening implementation behind the neutral contract."""

    variant_id = "huian.two_player.v0_1"

    def plan_opening(self, wall, dealer, dice_total):
        return plan_opening(wall, dealer, dice_total)

def deal_initial_hands(wall, dealer):
    """Deal 16 alternating tiles, then the dealer's seventeenth tile.

    This order is a deterministic simulator convention.  It does not claim to
    reproduce the physical multi-tile dealing animation.
    """
    if dealer not in (0, 1):
        raise ValueError("dealer must be seat 0 or 1")
    working = list(wall)
    if len(working) < 33:
        raise ValueError("Wall cannot supply initial two-player hands")
    hands = [[], []]
    order = (dealer, 1 - dealer)
    for _ in range(16):
        for player in order:
            hands[player].append(working.pop(0))
    hands[dealer].append(working.pop(0))
    return hands, working


def locate_gold_indicator(wall, dice_total):
    """Locate the top tile of the Nth two-tile stack counted from the tail.

    A flower at that location is skipped toward the tail until a normal tile is
    found.  The wall itself is not mutated.
    """
    if type(dice_total) is not int or not 2 <= dice_total <= 12:
        raise ValueError("Two-dice total must be an integer from 2 to 12")
    start = len(wall) - (2 * dice_total - 1)
    if start < 0:
        raise ValueError("Wall is too short for the dice-selected stack")
    skipped = []
    for index in range(start, len(wall)):
        tile = wall[index]
        if tile not in env.FLOWERS:
            return GoldIndicator(tile, index, tuple(skipped))
        skipped.append(tile)
    raise ValueError("No non-flower tile available while opening gold")


def plan_opening(wall, dealer, dice_total):
    """Build opening zones through dealer-first flower replacement and gold lookup."""
    hands, remaining = deal_initial_hands(deepcopy(wall), dealer)
    replacement = replace_flowers(hands, [[], []], remaining, dealer)
    indicator = locate_gold_indicator(replacement.wall, dice_total)
    return OpeningPlan(dealer, replacement.hands, replacement.flowers,
                       replacement.wall, replacement, indicator)
