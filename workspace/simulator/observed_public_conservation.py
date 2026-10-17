"""Partial physical accounting for a reviewed hand with hidden tiles.

Only explicitly observed public zones and a terminal concealed snapshot are
counted. Unseen hands/wall stay UNKNOWN; this cannot construct GameState or
claim that the full 144-tile environment invariant has been replayed.
"""
from collections import Counter
from dataclasses import dataclass

from huian._legacy import core


@dataclass(frozen=True)
class PublicTileEvent:
    kind: str  # RIVER, OFFER, CLAIM, or RESOLVE_RIVER
    actor: str
    tile: str | None = None
    meld: tuple[str, ...] = ()


def audit_public_conservation(events, *, terminal_concealed=(),
                              opened_gold=None, flower_count=0,
                              observed_wall_remaining=None,
                              observed_terminal_river_counts=None,
                              terminal_concealed_by_actor=None,
                              observed_terminal_meld_tile_counts=None,
                              observed_terminal_flower_counts=None):
    """Check that a claimed offer moves exactly once and no known type has 5 copies.

    CLAIM meld contains the offered tile plus the claimant's own two/three
    tiles. No hidden hand is reconstructed from this evidence.
    """
    if type(flower_count) is not int or not 0 <= flower_count <= 8:
        raise ValueError("flower_count must be an observed count from 0 to 8")
    if opened_gold is not None and opened_gold not in core.BASE_TILES:
        raise ValueError("opened gold must be a normal tile")
    if (observed_wall_remaining is not None
            and (type(observed_wall_remaining) is not int
                 or not 0 <= observed_wall_remaining <= 144)):
        raise ValueError("wall observation must be an integer from 0 to 144")
    if observed_terminal_river_counts is not None:
        if (type(observed_terminal_river_counts) is not dict
                or set(observed_terminal_river_counts) != {"tz", "opponent"}
                or any(type(value) is not int or not 0 <= value <= 144
                       for value in observed_terminal_river_counts.values())):
            raise ValueError("terminal river observation requires integer counts for both actors")
    for label, values, upper in (
        ("terminal concealed", terminal_concealed_by_actor, 144),
        ("terminal meld", observed_terminal_meld_tile_counts, 144),
        ("terminal flower", observed_terminal_flower_counts, 8),
    ):
        if values is not None and (type(values) is not dict
                or set(values) != {"tz", "opponent"}):
            raise ValueError(f"{label} observation requires both actors")
        if values is not None and label == "terminal concealed":
            if any(type(tiles) not in (list, tuple) for tiles in values.values()):
                raise ValueError("terminal concealed values must be tile sequences")
        elif values is not None and any(type(value) is not int or not 0 <= value <= upper
                                         for value in values.values()):
            raise ValueError(f"{label} counts must be nonnegative integers")
    if terminal_concealed_by_actor is not None and terminal_concealed:
        raise ValueError("provide terminal concealed tiles in one format only")
    if observed_terminal_flower_counts is not None and sum(
            observed_terminal_flower_counts.values()) != flower_count:
        raise ValueError("terminal flower counts disagree with flower_count")
    counts = Counter()
    pending = None
    rivers = Counter()
    melds = []

    def add(tile):
        if tile not in core.BASE_TILES:
            raise ValueError(f"invalid observed tile: {tile!r}")
        counts[tile] += 1
        if counts[tile] > 4:
            raise ValueError(f"fifth known physical copy: {tile}")

    for event in events:
        if not isinstance(event, PublicTileEvent) or event.actor not in ("tz", "opponent"):
            raise ValueError("invalid public tile event or actor")
        if event.kind == "RIVER":
            if pending is not None or event.meld:
                raise ValueError("resolve the prior offer before another river change")
            add(event.tile)
            rivers[(event.actor, event.tile)] += 1
        elif event.kind == "OFFER":
            if pending is not None or event.meld:
                raise ValueError("an earlier action-area offer is unresolved")
            add(event.tile)
            pending = (event.actor, event.tile)
        elif event.kind == "CLAIM":
            if pending is None or event.actor == pending[0] or event.tile != pending[1]:
                raise ValueError("claim requires the opponent's exact pending offer")
            if len(event.meld) not in (3, 4) or event.tile not in event.meld:
                raise ValueError("claim meld does not consume its offered tile exactly")
            if len(event.meld) == 4 and event.meld != (event.tile,) * 4:
                raise ValueError("kong must have four identical tiles")
            if len(event.meld) == 3 and event.meld.count(event.tile) == 1:
                ordered = sorted(event.meld)
                if (any(tile not in core.BASE_TILES for tile in ordered)
                        or len({tile[0] for tile in ordered}) != 1
                        or ordered[0][0] not in "MPS"
                        or [int(tile[1]) for tile in ordered]
                        != list(range(int(ordered[0][1]), int(ordered[0][1]) + 3))):
                    raise ValueError("chi must be a suited consecutive sequence")
            elif len(event.meld) == 3 and event.meld != (event.tile,) * 3:
                raise ValueError("peng must have three identical tiles")
            remaining = list(event.meld)
            remaining.remove(event.tile)  # OFFER already counted this copy.
            for tile in remaining:
                add(tile)
            melds.append((event.actor, event.meld))
            pending = None
        elif event.kind == "RESOLVE_RIVER":
            if pending != (event.actor, event.tile) or event.meld:
                raise ValueError("river resolution requires the exact pending offer")
            rivers[(event.actor, event.tile)] += 1
            pending = None
        else:
            raise ValueError("unsupported public event kind")
    if pending is not None:
        raise ValueError("unresolved action-area offer at checkpoint")
    concealed = terminal_concealed
    if terminal_concealed_by_actor is not None:
        concealed = tuple(tile for actor in ("tz", "opponent")
                          for tile in terminal_concealed_by_actor[actor])
    for tile in concealed:
        add(tile)
    if opened_gold is not None:
        add(opened_gold)
    river_counts_by_actor = {
        actor: sum(count for (owner, _tile), count in rivers.items() if owner == actor)
        for actor in ("tz", "opponent")
    }
    if observed_terminal_river_counts is not None:
        for actor in ("tz", "opponent"):
            expected = observed_terminal_river_counts[actor]
            actual = river_counts_by_actor[actor]
            if actual != expected:
                raise ValueError(
                    f"{actor} river count mismatch: ledger={actual}, observed={expected}"
                )
    meld_tile_counts_by_actor = {
        actor: sum(len(tiles) for owner, tiles in melds if owner == actor)
        for actor in ("tz", "opponent")
    }
    if observed_terminal_meld_tile_counts is not None:
        for actor in ("tz", "opponent"):
            expected = observed_terminal_meld_tile_counts[actor]
            actual = meld_tile_counts_by_actor[actor]
            if actual != expected:
                raise ValueError(
                    f"{actor} meld tile count mismatch: ledger={actual}, observed={expected}"
                )
    hand_meld_counts_by_actor = None
    if terminal_concealed_by_actor is not None:
        hand_meld_counts_by_actor = {
            actor: len(terminal_concealed_by_actor[actor]) + meld_tile_counts_by_actor[actor]
            for actor in ("tz", "opponent")
        }
    known = sum(counts.values()) + flower_count
    if known > 144:
        raise ValueError("known zones exceed the 144-tile wall")
    nonwall_gap = None
    if observed_wall_remaining is not None:
        nonwall_gap = 144 - known - observed_wall_remaining
        if nonwall_gap < 0:
            raise ValueError("known zones and observed wall exceed 144 tiles")
    return {
        "known_physical_tile_count": known,
        "unknown_physical_tile_count": 144 - known,
        "conditional_unlocated_nonwall_count": nonwall_gap,
        "known_type_counts": dict(sorted(counts.items())),
        "river_tile_count": sum(rivers.values()),
        "river_tile_counts_by_actor": river_counts_by_actor,
        "terminal_river_counts_verified": observed_terminal_river_counts is not None,
        "meld_count": len(melds),
        "meld_tile_counts_by_actor": meld_tile_counts_by_actor,
        "terminal_hand_meld_tile_counts_by_actor": hand_meld_counts_by_actor,
        "terminal_meld_tile_counts_verified": observed_terminal_meld_tile_counts is not None,
        "terminal_flower_counts_verified": observed_terminal_flower_counts is not None,
        "known_tile_copy_bound_verified": True,
        "full_144_tile_conservation_verified": False,
    }
