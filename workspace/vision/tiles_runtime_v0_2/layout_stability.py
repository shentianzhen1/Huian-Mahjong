"""Geometry-only bottom-layout inspection for Huian replay frames.

This is deliberately not a tile classifier.  It finds bright, tile-shaped
components in a broad bottom band, then marks a spatially isolated rightmost
component as a *possible* draw.  Meld-vs-concealed-hand semantics remain a
human-reviewed state question.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image


@dataclass(frozen=True)
class TileComponent:
    bbox: tuple[int, int, int, int]


@dataclass(frozen=True)
class BottomLayout:
    components: tuple[TileComponent, ...]
    possible_draw: TileComponent | None
    gold_component: TileComponent | None
    hand_component_count: int
    notes: tuple[str, ...]


def detect_bottom_layout(image: Image.Image) -> BottomLayout:
    """Return conservative bright tile-face components from the bottom band."""
    frame = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    height, width = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mask = (gray > 150).astype(np.uint8) * 255
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    boxes = []
    for x, y, box_width, box_height, area in stats[1:count]:
        if not (y >= height * 0.78 and box_height >= height * 0.08):
            continue
        if not (width * 0.015 <= box_width <= width * 0.075):
            continue
        if area < box_width * box_height * 0.28:
            continue
        boxes.append(TileComponent((int(x), int(y), int(box_width), int(box_height))))
    boxes.sort(key=lambda item: item.bbox[0])
    if not boxes:
        return BottomLayout((), None, None, 0, ("no_tile_components",))

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    yellow = cv2.inRange(hsv, (15, 70, 100), (45, 255, 255))
    yellow_count, _, yellow_stats, _ = cv2.connectedComponentsWithStats(yellow, 8)
    gold_candidates = []
    for x, y, box_width, box_height, area in yellow_stats[1:yellow_count]:
        if y < height * 0.78 or area < width * height * 0.003:
            continue
        if not (width * 0.02 <= box_width <= width * 0.07):
            continue
        if not (height * 0.08 <= box_height <= height * 0.18):
            continue
        gold_candidates.append(TileComponent((int(x), int(y), int(box_width), int(box_height))))
    gold_component = max(gold_candidates, key=lambda item: item.bbox[2] * item.bbox[3], default=None)
    if gold_component is not None:
        gx, gy, gw, gh = gold_component.bbox

        def overlaps_gold(component: TileComponent) -> bool:
            x, y, box_width, box_height = component.bbox
            return x < gx + gw and gx < x + box_width and y < gy + gh and gy < y + box_height

        boxes = [component for component in boxes if not overlaps_gold(component)]

    widths = sorted(item.bbox[2] for item in boxes)
    median_width = widths[len(widths) // 2]
    possible_draw = None
    if len(boxes) >= 2:
        before, last = boxes[-2], boxes[-1]
        gap = last.bbox[0] - (before.bbox[0] + before.bbox[2])
        if gap > median_width * 0.55:
            possible_draw = last
    notes = ["geometry_only", "meld_vs_hand_requires_review"]
    if possible_draw is None:
        notes.append("draw_not_separated")
    return BottomLayout(tuple(boxes), possible_draw, gold_component,
                        len(boxes) - int(possible_draw is not None),
                        tuple(notes))
