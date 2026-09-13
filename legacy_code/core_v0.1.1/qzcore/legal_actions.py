
from collections import Counter
from .tiles import is_suited, suit_rank, BASE_TILES

def can_peng(hand, discard, gold_tile=None):
    # Do not consume gold as a substitute for a claimed pung.
    if discard == gold_tile:
        return False
    return Counter(hand)[discard] >= 2

def can_ming_gang(hand, discard, gold_tile=None):
    if discard == gold_tile:
        return False
    return Counter(hand)[discard] >= 3

def can_an_gang(hand, tile, gold_tile=None):
    if tile == gold_tile:
        return False
    return Counter(hand)[tile] >= 4

def chi_options(hand, discard, allow_chi=False, gold_tile=None):
    if allow_chi is not True or not is_suited(discard) or discard == gold_tile:
        return []
    suit, rank = suit_rank(discard)
    c = Counter(hand)
    opts = []
    for start in (rank-2, rank-1, rank):
        if not 1 <= start <= 7:
            continue
        seq = [f"{suit}{start+i}" for i in range(3)]
        need = [t for t in seq if t != discard]
        if len(need) == 2 and all(c[t] >= need.count(t) for t in set(need)):
            opts.append(tuple(seq))
    return opts
