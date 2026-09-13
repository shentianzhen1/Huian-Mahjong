
from functools import lru_cache
from collections import Counter
from .tiles import BASE_TILES, is_suited, suit_rank, index_tile, tile_index, validate_tile_multiset, CN

def _load_default_rules():
    # Keep logic self-contained; exact room overrides are passed as args.
    return {
        "single_gold_can_pinghu": False,
        "double_gold_can_pinghu": False,
    }

def _counts_without_gold(tiles, gold_tile):
    counts = [0]*len(BASE_TILES)
    golds = 0
    for t in tiles:
        if t == gold_tile:
            golds += 1
        else:
            counts[tile_index(t)] += 1
    return tuple(counts), golds

def _sequence_starts_for_index(i):
    tile = index_tile(i)
    sr = suit_rank(tile)
    if not sr:
        return []
    suit, rank = sr
    starts = []
    for start in (rank-2, rank-1, rank):
        if 1 <= start <= 7:
            ids = [tile_index(f"{suit}{start+j}") for j in range(3)]
            if i in ids:
                starts.append(ids)
    return starts

def winning_decompositions(tiles, gold_tile=None, open_melds=0, max_solutions=20):
    """
    Return structural winning decompositions for Quanzhou-style 17-tile hand:
    total structure = 5 melds + 1 pair.
    open_melds reduces the number of concealed melds required.

    Gold copies are treated as wildcards.
    Flowers must already be removed via replacement.
    """
    ok,msg = validate_tile_multiset(tiles, include_flowers=False)
    if not ok:
        return []

    groups_needed = 5 - int(open_melds)
    if groups_needed < 0:
        return []

    expected = groups_needed*3 + 2
    if len(tiles) != expected:
        return []

    if gold_tile is not None and gold_tile not in BASE_TILES:
        return []

    counts, golds = _counts_without_gold(tiles, gold_tile) if gold_tile else (
        tuple(Counter(tiles).get(t,0) for t in BASE_TILES), 0
    )

    solutions = []

    @lru_cache(None)
    def solve_groups(counts_t, g, groups_left):
        counts_l = list(counts_t)
        total = sum(counts_l) + g
        if total != groups_left*3:
            return tuple()
        if groups_left == 0:
            return (tuple(),) if total == 0 else tuple()

        try:
            i = next(j for j,n in enumerate(counts_l) if n)
        except StopIteration:
            if g == groups_left*3:
                return (tuple((("GOLD","GOLD","GOLD"),) for _ in range(1)),) if groups_left == 1 else (
                    (tuple(("GOLD","GOLD","GOLD") for _ in range(groups_left))),)
            return tuple()

        out = []

        # Triplet using natural copies + gold fill
        need = max(0, 3-counts_l[i])
        use_nat = min(3, counts_l[i])
        if need <= g and use_nat >= 1:
            newc = counts_l[:]
            newc[i] -= use_nat
            group = tuple([index_tile(i)]*use_nat + ["GOLD"]*need)
            for tail in solve_groups(tuple(newc), g-need, groups_left-1):
                out.append((group,) + tail)
                if len(out) >= max_solutions:
                    return tuple(out)

        # Sequences containing the lowest natural tile; missing members may be gold.
        for ids in _sequence_starts_for_index(i):
            newc = counts_l[:]
            group = []
            missing = 0
            consumed_i = False
            for j in ids:
                if newc[j] > 0:
                    newc[j] -= 1
                    group.append(index_tile(j))
                    if j == i:
                        consumed_i = True
                else:
                    missing += 1
                    group.append("GOLD")
            if consumed_i and missing <= g:
                for tail in solve_groups(tuple(newc), g-missing, groups_left-1):
                    out.append((tuple(group),) + tail)
                    if len(out) >= max_solutions:
                        return tuple(out)

        return tuple(out)

    # Pair from two naturals
    counts_l = list(counts)
    for i,n in enumerate(counts_l):
        if n >= 2:
            newc = counts_l[:]
            newc[i] -= 2
            for groups in solve_groups(tuple(newc), golds, groups_needed):
                solutions.append({"pair": (index_tile(i), index_tile(i)), "groups": list(groups)})
                if len(solutions) >= max_solutions:
                    return solutions

    # Pair from one natural + one gold
    if golds >= 1:
        for i,n in enumerate(counts_l):
            if n >= 1:
                newc = counts_l[:]
                newc[i] -= 1
                for groups in solve_groups(tuple(newc), golds-1, groups_needed):
                    solutions.append({"pair": (index_tile(i), "GOLD"), "groups": list(groups)})
                    if len(solutions) >= max_solutions:
                        return solutions

    # Pair from two golds
    if golds >= 2:
        for groups in solve_groups(tuple(counts_l), golds-2, groups_needed):
            solutions.append({"pair": ("GOLD","GOLD"), "groups": list(groups)})
            if len(solutions) >= max_solutions:
                return solutions

    return solutions

def can_win(tiles, gold_tile=None, open_melds=0, win_type="zimo",
            single_gold_can_pinghu=False, double_gold_can_pinghu=False):
    """
    win_type: zimo / pinghu / qianggang / ...
    Quanzhou confirmed rule: single gold can pinghu; double gold cannot pinghu.
    """
    if gold_tile:
        gold_count = sum(1 for t in tiles if t == gold_tile)
        if win_type == "pinghu":
            if gold_count == 1 and not single_gold_can_pinghu:
                return False
            if gold_count >= 2 and not double_gold_can_pinghu:
                return False
    return bool(winning_decompositions(tiles, gold_tile=gold_tile, open_melds=open_melds))
