
from collections import Counter
from .tiles import is_honor, FLOWERS, CN
from .models import MeldKind

CONFIRMED = {
    "gold_each": 1,
    "flower_each": 1,
    "concealed_triplet_suited": 1,
    "concealed_triplet_honor": 2,
    "open_pung_honor": 1,
    "ming_gang_suited": 2,
    "ming_gang_honor": 3,
    "an_gang_suited": 3,
    "an_gang_honor": 4,
    "spring_summer_autumn_winter": 8,
    "plum_orchid_bamboo_chrysanthemum": 8,
    "all_eight_flowers": 16,
}

def flower_bonus_candidates(flowers):
    s = set(flowers)
    candidates = []
    if set(("F1","F2","F3","F4")).issubset(s):
        candidates.append(("春夏秋冬", 8))
    if set(("F5","F6","F7","F8")).issubset(s):
        candidates.append(("梅兰竹菊", 8))
    if set(FLOWERS).issubset(s):
        candidates.append(("八花齐", 16))
    return candidates

def calculate_confirmed_atomic_fan(gold_count=0, flowers=(), melds=(), concealed_groups=()):
    """
    Returns only atomic fan items we can encode with high confidence.
    Flower-set stacking is returned separately as candidates because stacking/de-duplication
    still needs an exact two-player settlement confirmation.
    """
    items = []
    if gold_count:
        items.append((f"金牌×{gold_count}", gold_count*CONFIRMED["gold_each"]))
    if flowers:
        items.append((f"花牌×{len(flowers)}", len(flowers)*CONFIRMED["flower_each"]))

    for meld in melds:
        t = meld.tiles[0] if meld.tiles else None
        honor = is_honor(t) if t else False
        if meld.kind == MeldKind.PENG and honor:
            items.append(("字牌碰", CONFIRMED["open_pung_honor"]))
        elif meld.kind == MeldKind.MING_GANG:
            items.append(("字牌明杠" if honor else "明杠",
                          CONFIRMED["ming_gang_honor"] if honor else CONFIRMED["ming_gang_suited"]))
        elif meld.kind == MeldKind.AN_GANG:
            items.append(("字牌暗杠" if honor else "暗杠",
                          CONFIRMED["an_gang_honor"] if honor else CONFIRMED["an_gang_suited"]))

    # Only count fully-natural concealed triplets here (no GOLD tokens).
    for g in concealed_groups:
        if len(g) == 3 and g[0] == g[1] == g[2] and g[0] != "GOLD":
            if is_honor(g[0]):
                items.append(("字牌暗刻", CONFIRMED["concealed_triplet_honor"]))
            else:
                items.append(("暗刻", CONFIRMED["concealed_triplet_suited"]))

    total = sum(v for _,v in items)
    return {
        "confirmed_atomic_total": total,
        "items": items,
        "flower_bonus_candidates": flower_bonus_candidates(flowers),
        "note": "组合花番的叠加/替代方式仍待二人实战结算确认，因此未自动并入总番。"
    }
