"""Stable tile identifiers shared by data labels and offline inference."""

SUITED = {
    **{f"M{rank}": "wan" for rank in range(1, 10)},
    **{f"P{rank}": "tong" for rank in range(1, 10)},
    **{f"S{rank}": "tiao" for rank in range(1, 10)},
}
HONORS = {
    "E": "honor", "SOUTH": "honor", "W": "honor", "N": "honor",
    "R": "honor", "G": "honor", "B": "honor",
}
FLOWERS = {f"F{index}": "flower" for index in range(1, 9)}
TILE_CLASSES = {**SUITED, **HONORS, **FLOWERS}


def category_for(tile_id):
    """Return the visual category or reject an unlabelled identifier."""
    try:
        return TILE_CLASSES[tile_id]
    except KeyError as exc:
        raise ValueError(f"Unknown tile class: {tile_id}") from exc
