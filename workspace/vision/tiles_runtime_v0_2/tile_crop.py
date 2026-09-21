"""Neighbor-safe classification crops derived from geometry components."""
from __future__ import annotations


def classification_crop_bbox(
    bbox: list[int] | tuple[int, int, int, int],
    *,
    frame_size: tuple[int, int],
    neighbors: list[list[int]] | tuple[tuple[int, int, int, int], ...] = (),
) -> tuple[int, int, int, int]:
    """Expand a geometry bbox without crossing an adjacent tile midpoint.

    Geometry boxes describe the detected bright component. Classification
    needs the complete tile face, especially for edge-heavy glyphs such as
    P9. Vertical padding is larger because the previous detector commonly
    clipped the tile crown; horizontal expansion is clamped by neighboring
    components so a crop never borrows pips/glyphs from the next tile.
    """
    x, y, width, height = (int(value) for value in bbox)
    frame_width, frame_height = frame_size
    left_pad = max(2, round(width * 0.08))
    right_pad = max(2, round(width * 0.08))
    top_pad = max(5, round(height * 0.14))
    bottom_pad = max(2, round(height * 0.05))

    for neighbor in neighbors:
        nx, ny, nw, nh = (int(value) for value in neighbor)
        vertical_overlap = max(0, min(y + height, ny + nh) - max(y, ny))
        if vertical_overlap < 0.35 * min(height, nh):
            continue
        if nx + nw <= x:
            gap = x - (nx + nw)
            left_pad = min(left_pad, max(0, gap // 2))
        elif nx >= x + width:
            gap = nx - (x + width)
            right_pad = min(right_pad, max(0, gap // 2))

    left = max(0, x - left_pad)
    top = max(0, y - top_pad)
    right = min(frame_width, x + width + right_pad)
    bottom = min(frame_height, y + height + bottom_pad)
    return left, top, right - left, bottom - top
