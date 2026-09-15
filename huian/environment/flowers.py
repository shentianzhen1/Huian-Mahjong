"""High-confidence two-player flower replacement rounds.

The caller supplies a wall whose tail is at the end of the list.  A flower
drawn while replacing is deliberately left until the next dealer-to-idle round.
"""
from copy import deepcopy
from dataclasses import dataclass

from huian._legacy import env


@dataclass(frozen=True)
class FlowerReplacement:
    player: int
    flowers: tuple[str, ...]
    replacements: tuple[str, ...]
    round_number: int


@dataclass(frozen=True)
class FlowerReplacementResult:
    hands: tuple[tuple[str, ...], tuple[str, ...]]
    flowers: tuple[tuple[str, ...], tuple[str, ...]]
    wall: tuple[str, ...]
    events: tuple[FlowerReplacement, ...]


def replace_flowers(hands, flowers, wall, dealer, *, minimum_wall_remaining=0):
    """Run dealer-first flower rounds until a complete round draws no flower."""
    if dealer not in (0, 1):
        raise ValueError("dealer must be seat 0 or 1")
    if type(minimum_wall_remaining) is not int or minimum_wall_remaining < 0:
        raise ValueError("minimum_wall_remaining must be nonnegative")
    if len(hands) != 2 or len(flowers) != 2:
        raise ValueError("Two player zones are required")
    working_hands = deepcopy(hands)
    working_flowers = deepcopy(flowers)
    working_wall = list(wall)
    if any(tile not in env.FLOWERS for zone in working_flowers for tile in zone):
        raise ValueError("Flower zone contains a non-flower tile")

    events = []
    order = (dealer, 1 - dealer)
    round_number = 0
    while True:
        round_number += 1
        new_flower = False
        for player in order:
            removed = tuple(tile for tile in working_hands[player] if tile in env.FLOWERS)
            if not removed:
                continue
            if minimum_wall_remaining and len(working_wall) - len(removed) < minimum_wall_remaining:
                # Keep unreplaced flowers in hand; the caller owns the boundary
                # state and must not treat incomplete replacement as a draw.
                return FlowerReplacementResult(
                    tuple(tuple(zone) for zone in working_hands),
                    tuple(tuple(zone) for zone in working_flowers),
                    tuple(working_wall), tuple(events))
            working_hands[player] = [tile for tile in working_hands[player] if tile not in env.FLOWERS]
            if len(working_wall) < len(removed):
                raise ValueError("Wall exhausted during flower replacement")
            replacements = tuple(working_wall.pop() for _ in removed)
            working_hands[player].extend(replacements)
            working_flowers[player].extend(removed)
            new_flower = new_flower or any(tile in env.FLOWERS for tile in replacements)
            events.append(FlowerReplacement(player, removed, replacements, round_number))
        if not new_flower:
            break

    return FlowerReplacementResult(
        tuple(tuple(zone) for zone in working_hands),
        tuple(tuple(zone) for zone in working_flowers),
        tuple(working_wall),
        tuple(events),
    )
