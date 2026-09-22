
from collections import Counter
from .tiles import BASE_TILES, validate_tile_multiset
from .win_checker import can_win

def ting_tiles(hand, gold_tile=None, open_melds=0, win_type="zimo",
               visible_counts=None, single_gold_can_pinghu=False, double_gold_can_pinghu=False):
    """
    hand should be one tile short of a structurally complete winning hand.
    Returns list of dicts: {"tile": code, "remaining": estimated_remaining_or_None}
    """
    ok,_ = validate_tile_multiset(hand, include_flowers=False)
    if not ok:
        return []

    c = Counter(hand)
    visible_counts = Counter(visible_counts or [])
    out = []
    for t in BASE_TILES:
        known = c[t] + visible_counts[t]
        if known >= 4:
            continue
        candidate = list(hand) + [t]
        if can_win(candidate, gold_tile=gold_tile, open_melds=open_melds, win_type=win_type,
                   single_gold_can_pinghu=single_gold_can_pinghu,
                   double_gold_can_pinghu=double_gold_can_pinghu):
            rem = max(0, 4-known)
            out.append({"tile": t, "remaining": rem})
    return out
