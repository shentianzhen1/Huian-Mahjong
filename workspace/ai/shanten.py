"""Huian ordinary-hand shanten and effective-tile analysis.

V0.1 covers only the ordinary 5-meld + 1-pair structure used by the
16/17-tile Huian hand. Fixed open melds reduce concealed melds required,
gold copies are structural wildcards, and special wins stay outside this layer.

Shanten convention:
- -1: ordinary structural Hu is complete
-  0: one effective draw away
-  1+: improvement layers away from tenpai
"""
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

from huian._legacy import core


@dataclass(frozen=True)
class EffectiveTile:
    tile: str
    remaining: int
    next_shanten: int
    winning: bool


@dataclass(frozen=True)
class HandEfficiency:
    shanten: int
    effective_tiles: tuple[EffectiveTile, ...]
    total_live_copies: int
    open_melds: int
    gold_count: int

    @property
    def effective_tile_types(self):
        return tuple(item.tile for item in self.effective_tiles)


@dataclass(frozen=True)
class DiscardEfficiency:
    discard: str
    shanten: int
    effective_tiles: tuple[EffectiveTile, ...]
    total_live_copies: int

    @property
    def effective_tile_types(self):
        return tuple(item.tile for item in self.effective_tiles)


def _validate_inputs(hand, gold_tile, open_melds):
    if isinstance(open_melds, bool) or not isinstance(open_melds, int):
        raise ValueError("open_melds must be an integer")
    if not 0 <= open_melds <= 5:
        raise ValueError("open_melds must be between 0 and 5")
    ok, message = core.validate_tile_multiset(hand, include_flowers=False)
    if not ok:
        raise ValueError(message)
    if gold_tile is not None and gold_tile not in core.BASE_TILES:
        raise ValueError("gold_tile must be a base tile or None")
    groups_needed = 5 - open_melds
    target = groups_needed * 3 + 2
    if len(hand) not in (target - 1, target):
        raise ValueError(
            f"ordinary efficiency expects {target - 1} or {target} concealed "
            f"tiles with {open_melds} fixed open melds"
        )
    return groups_needed, target


def _counts_without_gold(hand, gold_tile):
    counts = [0] * len(core.BASE_TILES)
    golds = 0
    for tile in hand:
        if gold_tile is not None and tile == gold_tile:
            golds += 1
        else:
            counts[core.tile_index(tile)] += 1
    return tuple(counts), golds


@lru_cache(maxsize=200000)
def _max_natural_used(counts, groups_needed):
    """Maximum natural tiles placeable into target meld/pair component slots."""
    total_natural = sum(counts)

    @lru_cache(maxsize=None)
    def search(counts_t, melds, taatsu, pair):
        try:
            index = next(i for i, value in enumerate(counts_t) if value)
        except StopIteration:
            effective_taatsu = min(taatsu, groups_needed - melds)
            extra_taatsu = taatsu - effective_taatsu
            consumed = 3 * melds + 2 * taatsu + 2 * pair
            skipped = total_natural - consumed
            if skipped < 0:
                return -1
            single_pool = skipped + 2 * extra_taatsu
            empty_components = (
                groups_needed - melds - effective_taatsu + (1 - pair)
            )
            return (
                3 * melds
                + 2 * effective_taatsu
                + 2 * pair
                + min(single_pool, empty_components)
            )

        counts_l = list(counts_t)
        best = -1

        counts_l[index] -= 1
        best = max(best, search(tuple(counts_l), melds, taatsu, pair))
        counts_l[index] += 1

        if melds < groups_needed and counts_l[index] >= 3:
            next_counts = counts_l[:]
            next_counts[index] -= 3
            best = max(
                best,
                search(tuple(next_counts), melds + 1, taatsu, pair),
            )

        tile = core.index_tile(index)
        suited = core.suit_rank(tile)
        if melds < groups_needed and suited is not None:
            suit, rank = suited
            if rank <= 7:
                ids = tuple(core.tile_index(f"{suit}{rank + offset}")
                            for offset in range(3))
                if all(counts_l[i] for i in ids):
                    next_counts = counts_l[:]
                    for i in ids:
                        next_counts[i] -= 1
                    best = max(
                        best,
                        search(tuple(next_counts), melds + 1, taatsu, pair),
                    )

        if counts_l[index] >= 2:
            if pair == 0:
                next_counts = counts_l[:]
                next_counts[index] -= 2
                best = max(
                    best,
                    search(tuple(next_counts), melds, taatsu, 1),
                )
            if taatsu < groups_needed:
                next_counts = counts_l[:]
                next_counts[index] -= 2
                best = max(
                    best,
                    search(tuple(next_counts), melds, taatsu + 1, pair),
                )

        if taatsu < groups_needed and suited is not None:
            suit, rank = suited
            for delta in (1, 2):
                other_rank = rank + delta
                if other_rank > 9:
                    continue
                other = core.tile_index(f"{suit}{other_rank}")
                if counts_l[other]:
                    next_counts = counts_l[:]
                    next_counts[index] -= 1
                    next_counts[other] -= 1
                    best = max(
                        best,
                        search(tuple(next_counts), melds, taatsu + 1, pair),
                    )

        return best

    return search(counts, 0, 0, 0)


@lru_cache(maxsize=200000)
def _ordinary_shanten_counts(counts, gold_count, groups_needed):
    target_slots = groups_needed * 3 + 2
    natural_used = _max_natural_used(counts, groups_needed)
    missing_before_gold = target_slots - natural_used
    missing_after_gold = max(0, missing_before_gold - gold_count)
    return missing_after_gold - 1


def ordinary_shanten(hand, gold_tile=None, open_melds=0):
    """Return ordinary structural shanten for a 16/17-style concealed zone."""
    groups_needed, _ = _validate_inputs(hand, gold_tile, open_melds)
    counts, gold_count = _counts_without_gold(tuple(hand), gold_tile)
    return _ordinary_shanten_counts(counts, gold_count, groups_needed)


def _public_counter(visible_tiles):
    visible = Counter(tile for tile in visible_tiles if tile in core.BASE_TILES)
    if any(value > 4 for value in visible.values()):
        raise ValueError("public visible base-tile count cannot exceed four")
    return visible


def analyze_effective_tiles(
        hand, gold_tile=None, open_melds=0, visible_tiles=()):
    """Analyze effective next draws for a pre-draw concealed hand.

    visible_tiles should contain public base tiles only, normally rivers and
    exposed melds. Opponent concealed tiles and wall order are not used.
    """
    groups_needed, target = _validate_inputs(hand, gold_tile, open_melds)
    if len(hand) != target - 1:
        raise ValueError("effective-tile analysis requires the pre-draw hand size")

    hand = tuple(hand)
    current = ordinary_shanten(hand, gold_tile, open_melds)
    public = _public_counter(tuple(visible_tiles))
    own = Counter(hand)
    if any(own[tile] + public[tile] > 4 for tile in core.BASE_TILES):
        raise ValueError("own concealed plus public visible copies exceed four")

    effective = []
    for tile in core.BASE_TILES:
        remaining = 4 - own[tile] - public[tile]
        if remaining <= 0:
            continue
        next_value = ordinary_shanten(
            (*hand, tile), gold_tile, open_melds)
        if next_value < current:
            effective.append(EffectiveTile(
                tile=tile,
                remaining=remaining,
                next_shanten=next_value,
                winning=next_value == -1,
            ))

    effective.sort(key=lambda item: core.tile_index(item.tile))
    return HandEfficiency(
        shanten=current,
        effective_tiles=tuple(effective),
        total_live_copies=sum(item.remaining for item in effective),
        open_melds=open_melds,
        gold_count=hand.count(gold_tile) if gold_tile is not None else 0,
    )


def rank_discards(hand, gold_tile=None, open_melds=0, visible_tiles=()):
    """Rank post-draw discards by shanten, then live effective copies."""
    _, target = _validate_inputs(hand, gold_tile, open_melds)
    if len(hand) != target:
        raise ValueError("discard ranking requires the post-draw hand size")

    hand = list(hand)
    visible_tiles = tuple(visible_tiles)
    candidates = []
    for discard in sorted(set(hand), key=core.tile_index):
        reduced = hand[:]
        reduced.remove(discard)
        analysis = analyze_effective_tiles(
            reduced,
            gold_tile=gold_tile,
            open_melds=open_melds,
            visible_tiles=(*visible_tiles, discard),
        )
        candidates.append(DiscardEfficiency(
            discard=discard,
            shanten=analysis.shanten,
            effective_tiles=analysis.effective_tiles,
            total_live_copies=analysis.total_live_copies,
        ))

    return tuple(sorted(
        candidates,
        key=lambda item: (
            item.shanten,
            -item.total_live_copies,
            -len(item.effective_tiles),
            core.tile_index(item.discard),
        ),
    ))



def best_discard(hand, gold_tile=None, open_melds=0, visible_tiles=(),
                 allowed_discards=None):
    """Return the best discard without fully expanding inferior-shanten options.

    Ranking is identical to rank_discards()[0]: minimum shanten first, then
    maximum live effective copies, then effective tile types, then tile order.
    """
    _, target = _validate_inputs(hand, gold_tile, open_melds)
    if len(hand) != target:
        raise ValueError("best_discard requires the post-draw hand size")

    hand = list(hand)
    if allowed_discards is None:
        allowed = set(hand)
    else:
        allowed = set(allowed_discards)
        if not allowed or any(tile not in hand for tile in allowed):
            raise ValueError("allowed_discards must be non-empty tiles in hand")

    reduced_by_discard = {}
    min_shanten = None
    for discard in sorted(allowed, key=core.tile_index):
        reduced = hand[:]
        reduced.remove(discard)
        value = ordinary_shanten(reduced, gold_tile, open_melds)
        reduced_by_discard[discard] = (reduced, value)
        min_shanten = value if min_shanten is None else min(min_shanten, value)

    visible_tiles = tuple(visible_tiles)
    finalists = []
    for discard, (reduced, value) in reduced_by_discard.items():
        if value != min_shanten:
            continue
        analysis = analyze_effective_tiles(
            reduced,
            gold_tile=gold_tile,
            open_melds=open_melds,
            visible_tiles=(*visible_tiles, discard),
        )
        finalists.append(DiscardEfficiency(
            discard=discard,
            shanten=analysis.shanten,
            effective_tiles=analysis.effective_tiles,
            total_live_copies=analysis.total_live_copies,
        ))

    return min(
        finalists,
        key=lambda item: (
            item.shanten,
            -item.total_live_copies,
            -len(item.effective_tiles),
            core.tile_index(item.discard),
        ),
    )
