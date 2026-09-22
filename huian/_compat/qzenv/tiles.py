
from collections import Counter

SUITS = ("M", "P", "S")  # 万 / 筒 / 条
HONORS = ("E", "SOUTH", "W", "N", "R", "G", "B")
FLOWERS = ("F1","F2","F3","F4","F5","F6","F7","F8")

BASE_TILES = tuple(
    [f"M{i}" for i in range(1,10)] +
    [f"P{i}" for i in range(1,10)] +
    [f"S{i}" for i in range(1,10)] +
    list(HONORS)
)

CN = {
    **{f"M{i}": f"{'一二三四五六七八九'[i-1]}万" for i in range(1,10)},
    **{f"P{i}": f"{'一二三四五六七八九'[i-1]}筒" for i in range(1,10)},
    **{f"S{i}": f"{'一二三四五六七八九'[i-1]}条" for i in range(1,10)},
    "E":"东","SOUTH":"南","W":"西","N":"北","R":"中","G":"发","B":"白",
    "F1":"春","F2":"夏","F3":"秋","F4":"冬",
    "F5":"梅","F6":"兰","F7":"竹","F8":"菊",
}

def full_wall():
    wall = []
    for t in BASE_TILES:
        wall.extend([t] * 4)
    wall.extend(FLOWERS)
    return wall

def validate_multiset(tiles):
    allowed = set(BASE_TILES) | set(FLOWERS)
    bad = [t for t in tiles if t not in allowed]
    if bad:
        return False, f"未知牌编码: {bad}"
    c = Counter(tiles)
    for t, n in c.items():
        if t in BASE_TILES and n > 4:
            return False, f"{CN.get(t,t)} 出现 {n} 张，超过4张"
        if t in FLOWERS and n > 1:
            return False, f"花牌 {CN.get(t,t)} 重复出现"
    return True, "OK"
