"""Resolution-normalized, geometry-only Mahjong tile observation.

The detector intentionally does not infer tile identity or Mahjong state.  It
finds visible bottom tile faces, separates a spatially isolated draw candidate,
and detects the yellow Gold tile independently of a fixed pixel location.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from statistics import median
from typing import Iterable

import cv2
import numpy as np
from PIL import Image


@dataclass(frozen=True)
class GeometryComponent:
    pixel_bbox: tuple[int, int, int, int]
    normalized_bbox: tuple[float, float, float, float]
    region_candidate: str
    confidence: float
    frame: str | int | None
    session: str | None

    def to_dict(self) -> dict:
        return {
            "pixel_bbox": list(self.pixel_bbox),
            "normalized_bbox": list(self.normalized_bbox),
            "region_candidate": self.region_candidate,
            "confidence": self.confidence,
            "frame": self.frame,
            "session": self.session,
        }


@dataclass(frozen=True)
class GeometryFrame:
    components: tuple[GeometryComponent, ...]
    geometry_untrusted: bool
    issues: tuple[str, ...]
    frame: str | int | None
    session: str | None

    def to_dict(self) -> dict:
        return {
            "components": [component.to_dict() for component in self.components],
            "geometry_untrusted": self.geometry_untrusted,
            "issues": list(self.issues),
            "frame": self.frame,
            "session": self.session,
            "safe_for_executor": False,
        }


def _normalized(box: tuple[int, int, int, int], width: int, height: int) -> tuple[float, ...]:
    x, y, box_width, box_height = box
    return tuple(round(value, 6) for value in (x / width, y / height, box_width / width, box_height / height))


def _overlaps(first: tuple[int, int, int, int], second: tuple[int, int, int, int]) -> bool:
    x, y, width, height = first
    other_x, other_y, other_width, other_height = second
    return x < other_x + other_width and other_x < x + width and y < other_y + other_height and other_y < y + height


def _bright_boxes(frame: np.ndarray) -> list[tuple[int, int, int, int]]:
    height, width = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mask = (gray > 150).astype(np.uint8) * 255
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    boxes = []
    for x, y, box_width, box_height, area in stats[1:count]:
        if y < height * 0.78 or box_height < height * 0.08:
            continue
        if not width * 0.015 <= box_width <= width * 0.075:
            continue
        if area < box_width * box_height * 0.28:
            continue
        boxes.append((int(x), int(y), int(box_width), int(box_height)))
    return sorted(boxes)


def _gold_box(frame: np.ndarray) -> tuple[int, int, int, int] | None:
    height, width = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    yellow = cv2.inRange(hsv, (15, 70, 100), (45, 255, 255))
    count, _, stats, _ = cv2.connectedComponentsWithStats(yellow, 8)
    candidates = []
    for x, y, box_width, box_height, area in stats[1:count]:
        if y < height * 0.78 or area < width * height * 0.003:
            continue
        if not width * 0.02 <= box_width <= width * 0.07:
            continue
        if not height * 0.08 <= box_height <= height * 0.18:
            continue
        candidates.append((int(x), int(y), int(box_width), int(box_height)))
    return max(candidates, key=lambda box: box[2] * box[3], default=None)


def detect_dynamic_geometry(image: Image.Image, *, frame: str | int | None = None,
                            session: str | None = None) -> GeometryFrame:
    """Observe hand/draw/gold candidates without a fixed layout or tile count."""
    array = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    height, width = array.shape[:2]
    gold = _gold_box(array)
    boxes = [box for box in _bright_boxes(array) if gold is None or not _overlaps(box, gold)]
    widths = [box[2] for box in boxes]
    typical_width = median(widths) if widths else 0.0
    draw = None
    if len(boxes) >= 2 and typical_width:
        prior, final = boxes[-2], boxes[-1]
        gap = final[0] - (prior[0] + prior[2])
        if gap > typical_width * 0.55:
            draw = final
    hand = [box for box in boxes if box != draw]
    issues = []
    if not hand:
        issues.append("no_hand_components")
    if len(hand) < 8 or len(hand) > 17:
        issues.append("component_count_outside_reviewed_range")
    if typical_width and hand:
        width_spread = (max(box[2] for box in hand) - min(box[2] for box in hand)) / typical_width
        if width_spread > 0.28:
            issues.append("component_size_inconsistent")
        gaps = [right[0] - (left[0] + left[2]) for left, right in zip(hand, hand[1:])]
        if any(gap > typical_width * 2.0 for gap in gaps):
            issues.append("fragmented_or_occluded_layout")
    if gold is None:
        issues.append("gold_unreadable")
    # A missing yellow Gold candidate must never be merged into hand, but it
    # does not invalidate an otherwise stable hand/draw geometry observation.
    # Occlusion/fragmentation and implausible hand counts remain fatal.
    untrusted = any(issue != "gold_unreadable" for issue in issues)
    components = []
    for box in hand:
        confidence = 0.92 if not untrusted else 0.60
        components.append(GeometryComponent(box, _normalized(box, width, height), "hand", confidence, frame, session))
    if draw is not None:
        components.append(GeometryComponent(draw, _normalized(draw, width, height), "draw", 0.88 if not untrusted else 0.58, frame, session))
    if gold is not None:
        components.append(GeometryComponent(gold, _normalized(gold, width, height), "gold", 0.90, frame, session))
    return GeometryFrame(tuple(components), untrusted, tuple(issues), frame, session)


def fuse_dynamic_geometry(frames: Iterable[GeometryFrame], minimum_frames: int = 3) -> GeometryFrame:
    """Accept a layout only after 3--5 trusted frames agree on region counts."""
    frames = list(frames)
    if minimum_frames < 3 or minimum_frames > 5:
        raise ValueError("minimum_frames must be within 3..5")
    trusted = [frame for frame in frames if not frame.geometry_untrusted]
    signatures = [tuple(sorted(Counter(component.region_candidate for component in frame.components).items())) for frame in trusted]
    if not signatures:
        return GeometryFrame((), True, ("no_trusted_frames",), None, None)
    winner, votes = Counter(signatures).most_common(1)[0]
    if votes < minimum_frames:
        return GeometryFrame((), True, ("layout_not_stable_across_frames",), None, None)
    chosen = next(frame for frame in reversed(trusted)
                  if tuple(sorted(Counter(component.region_candidate for component in frame.components).items())) == winner)
    return GeometryFrame(chosen.components, False, (f"stable_votes={votes}",), chosen.frame, chosen.session)
