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


@dataclass(frozen=True)
class TwoPlyOffense:
    """Deterministic next-draw / next-discard ordinary offense quality.

    All weighted fields use physical remaining base-tile copies as weights.
    This is an ordinary-hand lookahead signal, not score EV and not a special
    win model.
    """

    discard: str
    draw_copies: int
    terminal_win_copies: int
    weighted_post_shanten: int
    weighted_post_live_copies: int
    weighted_post_effective_types: int

    @property
    def expected_post_shanten(self):
        return self.weighted_post_shanten / self.draw_copies

    @property
    def expected_post_live_copies(self):
        return self.weighted_post_live_copies / self.draw_copies

    @property
    def expected_post_effective_types(self):
        return self.weighted_post_effective_types / self.draw_copies


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
    if gold_tile is not None and tuple(hand).count(gold_tile) > 3:
        raise ValueError("opened gold is non-drawable; concealed hand cannot contain four gold copies")
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
def _segment_states(counts, suited):
    """Return possible (melds, taatsu, pair_used) states for one tile segment.

    Segment caching is the performance-critical part of V0.1: the same local
    suit shape recurs across many candidate discards, draws, hands and matches.
    """
    @lru_cache(maxsize=None)
    def search(counts_t):
        try:
            index = next(i for i, value in enumerate(counts_t) if value)
        except StopIteration:
            return ((0, 0, 0),)

        counts_l = list(counts_t)
        out = set()

        # Leave one tile uncommitted as a single.
        counts_l[index] -= 1
        out.update(search(tuple(counts_l)))
        counts_l[index] += 1

        if counts_l[index] >= 3:
            next_counts = counts_l[:]
            next_counts[index] -= 3
            for melds, taatsu, pair in search(tuple(next_counts)):
                out.add((melds + 1, taatsu, pair))

        if suited and index <= 6 and all(
                counts_l[index + offset] for offset in (0, 1, 2)):
            next_counts = counts_l[:]
            for offset in (0, 1, 2):
                next_counts[index + offset] -= 1
            for melds, taatsu, pair in search(tuple(next_counts)):
                out.add((melds + 1, taatsu, pair))

        if counts_l[index] >= 2:
            next_counts = counts_l[:]
            next_counts[index] -= 2
            for melds, taatsu, pair in search(tuple(next_counts)):
                if pair == 0:
                    out.add((melds, taatsu, 1))
                out.add((melds, taatsu + 1, pair))

        if suited:
            for delta in (1, 2):
                other = index + delta
                if other >= len(counts_l) or not counts_l[other]:
                    continue
                next_counts = counts_l[:]
                next_counts[index] -= 1
                next_counts[other] -= 1
                for melds, taatsu, pair in search(tuple(next_counts)):
                    out.add((melds, taatsu + 1, pair))

        return tuple(sorted(out))

    return search(tuple(counts))


@lru_cache(maxsize=200000)
def _max_natural_used(counts, groups_needed):
    """Maximum natural tiles usable in the target structure via segment DP."""
    total_natural = sum(counts)
    segments = (
        _segment_states(counts[0:9], True),
        _segment_states(counts[9:18], True),
        _segment_states(counts[18:27], True),
        _segment_states(counts[27:34], False),
    )

    combined = {(0, 0, 0)}
    for segment in segments:
        next_states = set()
        for melds_a, taatsu_a, pair_a in combined:
            for melds_b, taatsu_b, pair_b in segment:
                melds = melds_a + melds_b
                taatsu = taatsu_a + taatsu_b
                pair = pair_a + pair_b
                if melds > groups_needed or taatsu > groups_needed or pair > 1:
                    continue
                next_states.add((melds, taatsu, pair))
        combined = next_states

    best = 0
    for melds, taatsu, pair in combined:
        effective_taatsu = min(taatsu, groups_needed - melds)
        extra_taatsu = taatsu - effective_taatsu
        consumed = 3 * melds + 2 * taatsu + 2 * pair
        skipped = total_natural - consumed
        if skipped < 0:
            continue
        single_pool = skipped + 2 * extra_taatsu
        empty_components = (
            groups_needed - melds - effective_taatsu + (1 - pair)
        )
        used = (
            3 * melds
            + 2 * effective_taatsu
            + 2 * pair
            + min(single_pool, empty_components)
        )
        best = max(best, used)
    return best


@lru_cache(maxsize=200000)
def _max_natural_used_melds_only(counts, groups_needed):
    """Maximum natural tiles placeable into meld-only structure.

    Used by the Jin/Youjin research layer after reserving one roaming Jin.
    Pairs are not a target component here; pair-shaped naturals may still be
    used as two-tile taatsu toward a triplet because _segment_states already
    emits that representation with pair_used=0.
    """
    total_natural = sum(counts)
    segments = (
        _segment_states(counts[0:9], True),
        _segment_states(counts[9:18], True),
        _segment_states(counts[18:27], True),
        _segment_states(counts[27:34], False),
    )

    combined = {(0, 0)}
    for segment in segments:
        next_states = set()
        for melds_a, taatsu_a in combined:
            for melds_b, taatsu_b, pair_b in segment:
                if pair_b:
                    continue
                melds = melds_a + melds_b
                taatsu = taatsu_a + taatsu_b
                if melds > groups_needed or taatsu > groups_needed:
                    continue
                next_states.add((melds, taatsu))
        combined = next_states

    best = 0
    for melds, taatsu in combined:
        effective_taatsu = min(taatsu, groups_needed - melds)
        extra_taatsu = taatsu - effective_taatsu
        consumed = 3 * melds + 2 * taatsu
        skipped = total_natural - consumed
        if skipped < 0:
            continue
        single_pool = skipped + 2 * extra_taatsu
        empty_components = groups_needed - melds - effective_taatsu
        used = (
            3 * melds
            + 2 * effective_taatsu
            + min(single_pool, empty_components)
        )
        best = max(best, used)
    return best


def youjin_meld_deficit(hand, gold_tile=None, open_melds=0):
    """Return structural deficit after reserving one roaming Jin.

    Input is a post-discard concealed hand (16 tiles with no open melds).
    One Jin is reserved as the roaming singleton. Remaining Jin copies act as
    wildcards inside melds. The result is the number of meld slots that still
    cannot be filled by the current tiles:

    - 0: structurally equivalent to confirmed single-Youjin-ready shape;
    - 1+: progressively farther from that meld-only target;
    - None: no Jin is available to reserve.

    This is a structural research metric, not a score EV and not a promise of
    exact draws-to-Youjin.
    """
    groups_needed, target = _validate_inputs(hand, gold_tile, open_melds)
    if len(hand) != target - 1:
        raise ValueError(
            "youjin_meld_deficit requires the post-discard concealed hand size"
        )
    if gold_tile is None or tuple(hand).count(gold_tile) < 1:
        return None

    counts, gold_count = _counts_without_gold(tuple(hand), gold_tile)
    natural_used = _max_natural_used_melds_only(counts, groups_needed)
    wildcard_gold = gold_count - 1
    missing_slots = groups_needed * 3 - natural_used
    return max(0, missing_slots - wildcard_gold)


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
    if any(
        own[tile] + public[tile] > (3 if tile == gold_tile else 4)
        for tile in core.BASE_TILES
    ):
        raise ValueError("own concealed plus public visible copies exceed physical capacity")

    effective = []
    for tile in core.BASE_TILES:
        capacity = 3 if tile == gold_tile else 4
        remaining = capacity - own[tile] - public[tile]
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



def min_shanten_discards(hand, gold_tile=None, open_melds=0, visible_tiles=(),
                         allowed_discards=None):
    """Return all minimum-shanten discard candidates with live-tile metrics.

    This preserves the two-stage performance strategy used by best_discard:
    first discard candidates are filtered by ordinary shanten, then only the
    minimum-shanten frontier expands effective tiles. Callers may apply an
    additional risk/EV model without ever selecting a worse-shanten discard.
    """
    _, target = _validate_inputs(hand, gold_tile, open_melds)
    if len(hand) != target:
        raise ValueError("min_shanten_discards requires the post-draw hand size")

    hand = list(hand)
    if allowed_discards is None:
        allowed = set(hand)
    else:
        allowed = set(allowed_discards)
        if not allowed or any(tile not in hand for tile in allowed):
            raise ValueError("allowed_discards must be non-empty tiles in hand")

    reduced_by_discard = {}
    min_value = None
    for discard in sorted(allowed, key=core.tile_index):
        reduced = hand[:]
        reduced.remove(discard)
        value = ordinary_shanten(reduced, gold_tile, open_melds)
        reduced_by_discard[discard] = (reduced, value)
        min_value = value if min_value is None else min(min_value, value)

    visible_tiles = tuple(visible_tiles)
    frontier = []
    for discard, (reduced, value) in reduced_by_discard.items():
        if value != min_value:
            continue
        analysis = analyze_effective_tiles(
            reduced,
            gold_tile=gold_tile,
            open_melds=open_melds,
            visible_tiles=(*visible_tiles, discard),
        )
        frontier.append(DiscardEfficiency(
            discard=discard,
            shanten=analysis.shanten,
            effective_tiles=analysis.effective_tiles,
            total_live_copies=analysis.total_live_copies,
        ))

    return tuple(sorted(
        frontier,
        key=lambda item: (
            -item.total_live_copies,
            -len(item.effective_tiles),
            core.tile_index(item.discard),
        ),
    ))


def best_offense_ties(hand, gold_tile=None, open_melds=0, visible_tiles=(),
                      allowed_discards=None):
    """Return candidates tied on every meaningful V0.3 offense metric.

    Candidates must share minimum shanten, maximum live effective copies and
    maximum effective-tile type count. The historical final tile-order tie
    break is intentionally omitted so a later model may choose only within a
    set that V0.3 considers offensively equivalent.
    """
    frontier = min_shanten_discards(
        hand, gold_tile=gold_tile, open_melds=open_melds,
        visible_tiles=visible_tiles, allowed_discards=allowed_discards)
    if not frontier:
        return ()
    best = frontier[0]
    return tuple(
        item for item in frontier
        if item.shanten == best.shanten
        and item.total_live_copies == best.total_live_copies
        and len(item.effective_tiles) == len(best.effective_tiles)
    )


def analyze_two_ply_offense(
        hand, candidate_discards, gold_tile=None, open_melds=0,
        visible_tiles=()):
    """Evaluate exact-offense-tie discards one ordinary draw further.

    For every physically possible next base-tile draw, terminal ordinary Hu is
    recorded directly. Otherwise the existing V0.3 policy chooses the best next
    discard, and the resulting shanten/live-copy/type metrics are accumulated.

    The caller should only compare candidates already tied on V0.3's current
    shanten/live-copy/type metrics. This function deliberately does not model
    opponent claims, special wins or settlement EV.
    """
    _, target = _validate_inputs(hand, gold_tile, open_melds)
    if len(hand) != target:
        raise ValueError("two-ply offense requires the post-draw hand size")
    hand = list(hand)
    candidates = tuple(dict.fromkeys(candidate_discards))
    if not candidates or any(tile not in hand for tile in candidates):
        raise ValueError("candidate_discards must be non-empty tiles in hand")

    visible_tiles = tuple(visible_tiles)
    results = []
    expected_draw_copies = None
    for discard in candidates:
        reduced = hand[:]
        reduced.remove(discard)
        visible_after_discard = (*visible_tiles, discard)
        public = _public_counter(visible_after_discard)
        own = Counter(reduced)
        if any(
            own[tile] + public[tile] > (3 if tile == gold_tile else 4)
            for tile in core.BASE_TILES
        ):
            raise ValueError("own concealed plus public visible copies exceed physical capacity")

        draw_copies = 0
        terminal_win_copies = 0
        weighted_post_shanten = 0
        weighted_post_live = 0
        weighted_post_types = 0

        for tile in core.BASE_TILES:
            capacity = 3 if tile == gold_tile else 4
            remaining = capacity - own[tile] - public[tile]
            if remaining <= 0:
                continue
            draw_copies += remaining
            drawn = (*reduced, tile)
            drawn_shanten = ordinary_shanten(
                drawn, gold_tile=gold_tile, open_melds=open_melds)
            if drawn_shanten == -1:
                terminal_win_copies += remaining
                post_shanten = -1
                post_live = 0
                post_types = 0
            else:
                next_choice = best_discard(
                    drawn,
                    gold_tile=gold_tile,
                    open_melds=open_melds,
                    visible_tiles=visible_after_discard,
                )
                post_shanten = next_choice.shanten
                post_live = next_choice.total_live_copies
                post_types = len(next_choice.effective_tiles)

            weighted_post_shanten += remaining * post_shanten
            weighted_post_live += remaining * post_live
            weighted_post_types += remaining * post_types

        if draw_copies <= 0:
            raise ValueError("public state leaves no possible next base-tile draw")
        if expected_draw_copies is None:
            expected_draw_copies = draw_copies
        elif draw_copies != expected_draw_copies:
            raise ValueError("candidate discards must preserve the same unseen draw count")

        results.append(TwoPlyOffense(
            discard=discard,
            draw_copies=draw_copies,
            terminal_win_copies=terminal_win_copies,
            weighted_post_shanten=weighted_post_shanten,
            weighted_post_live_copies=weighted_post_live,
            weighted_post_effective_types=weighted_post_types,
        ))
    return tuple(results)


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
