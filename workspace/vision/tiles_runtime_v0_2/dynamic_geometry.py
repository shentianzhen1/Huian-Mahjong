"""Resolution-normalized, geometry-only Mahjong tile observation.

The detector intentionally does not infer tile identity or Mahjong state.  It
finds visible bottom tile faces, separates a spatially isolated draw_visual candidate,
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


def _split_joined_component(
    box: tuple[int, int, int, int], mask: np.ndarray, typical_width: float
) -> list[tuple[int, int, int, int]]:
    """Split a connected bright component only when its width supports it.

    Adjacent tile faces can become one connected component through a bright
    border or artwork.  The split count comes from the observed median tile
    width, never from an expected hand count.  A local vertical projection
    selects a valley near each proportional division, with proportional
    division as a conservative fallback when the tile border has no valley.
    """
    x, y, width, height = box
    part_count = max(2, min(3, int(round(width / typical_width))))
    if part_count < 2:
        return [box]
    projection = mask[y:y + height, x:x + width].sum(axis=0)
    cuts: list[int] = []
    previous = 0
    for part in range(1, part_count):
        nominal = int(round(width * part / part_count))
        search_radius = max(2, int(round(typical_width * 0.28)))
        start = max(previous + 1, nominal - search_radius)
        end = min(width - 1, nominal + search_radius)
        if start >= end:
            cut = nominal
        else:
            cut = start + int(np.argmin(projection[start:end + 1]))
        # A valley inside tile artwork can be much closer to an edge than the
        # actual seam.  Reject such an unbalanced split and retain the
        # proportional boundary instead.
        minimum_part_width = max(2, int(round(typical_width * 0.75)))
        if cut - previous < minimum_part_width or width - cut < minimum_part_width:
            cut = nominal
        cuts.append(cut)
        previous = cut
    boundaries = [0, *cuts, width]
    return [
        (x + left, y, right - left, height)
        for left, right in zip(boundaries, boundaries[1:])
        if right > left
    ]


def _bright_boxes(frame: np.ndarray) -> list[tuple[int, int, int, int]]:
    height, width = frame.shape[:2]
    # HSV value preserves bright tile faces carrying saturated red/green art.
    # A grayscale threshold underweights those colours and can merge or lose
    # otherwise clear meld components.
    value = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)[:, :, 2]
    mask = (value > 150).astype(np.uint8) * 255
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    raw_boxes = []
    for x, y, box_width, box_height, area in stats[1:count]:
        if y < height * 0.78 or box_height < height * 0.08:
            continue
        # The wider upper bound is only an intake bound.  Oversized candidates
        # are split below using the measured width of neighbouring tile faces.
        if not width * 0.015 <= box_width <= width * 0.16:
            continue
        if area < box_width * box_height * 0.28:
            continue
        raw_boxes.append((int(x), int(y), int(box_width), int(box_height)))
    normal_boxes = [box for box in raw_boxes if box[2] <= width * 0.075]
    normal_widths = [box[2] for box in normal_boxes]
    typical_width = median(normal_widths) if normal_widths else 0.0
    typical_height = median([box[3] for box in normal_boxes]) if normal_boxes else 0.0
    boxes = []
    for box in raw_boxes:
        # Exposed/meld faces can be visibly shorter than upright concealed
        # tiles.  Height is only a guard against splitting wide UI panels; the
        # observed width still determines every split and no target count is
        # consulted.
        height_matches_tiles = typical_height and abs(box[3] - typical_height) <= typical_height * 0.25
        if typical_width and height_matches_tiles and box[2] > typical_width * 1.55:
            boxes.extend(_split_joined_component(box, mask, typical_width))
        elif box[2] <= width * 0.075:
            boxes.append(box)
        else:
            # A wide bright UI component is not evidence for a tile face.
            # Do not turn it into a speculative hand or meld candidate.
            continue
    return sorted(boxes)


def _clusters(
    boxes: list[tuple[int, int, int, int]], typical_width: float, *, gap_limit: float
) -> list[list[tuple[int, int, int, int]]]:
    """Group nearby components without using an absolute screen position."""
    if not boxes:
        return []
    ordered = sorted(boxes)
    groups = [[ordered[0]]]
    for box in ordered[1:]:
        previous = groups[-1][-1]
        gap = box[0] - (previous[0] + previous[2])
        baseline_delta = abs((box[1] + box[3]) - (previous[1] + previous[3]))
        # A raised/animated concealed tile can keep normal hand spacing while
        # its baseline moves appreciably.  Baseline remains a meld feature,
        # but does not fragment an otherwise consecutive hand run here.
        baseline_limit = median([item[3] for item in groups[-1]]) * 0.65
        if gap <= typical_width * gap_limit and baseline_delta <= baseline_limit:
            groups[-1].append(box)
        else:
            groups.append([box])
    return groups


def _orientation_deviation(mask: np.ndarray, box: tuple[int, int, int, int]) -> float:
    """Return the principal bright-pixel-axis deviation from an upright tile.

    This is intentionally a soft geometric feature: it complements baseline,
    aspect, spacing, and group size instead of deciding a region on its own.
    """
    x, y, width, height = box
    points = np.column_stack(np.nonzero(mask[y:y + height, x:x + width]))
    if len(points) < 20:
        return 0.0
    covariance = np.cov(points.astype(float), rowvar=False)
    values, vectors = np.linalg.eigh(covariance)
    axis = vectors[:, int(np.argmax(values))]
    # rows are y and columns are x; upright is aligned to the y axis.
    angle = abs(float(np.degrees(np.arctan2(axis[1], axis[0]))))
    return min(abs(angle), abs(180.0 - angle))


def _meld_like_group(
    group: list[tuple[int, int, int, int]],
    hand: list[tuple[int, int, int, int]],
    mask: np.ndarray,
    typical_width: float,
) -> bool:
    """Identify a compact, non-concealed group relative to the main hand.

    No absolute x coordinate or target hand count participates in this test.
    A candidate must be a small separated group and must visibly differ from
    the dominant hand in at least one of orientation, baseline, or aspect.
    """
    if not group or not hand:
        return False
    hand_baseline = median(item[1] + item[3] for item in hand)
    hand_aspect = median(item[3] / item[2] for item in hand)
    hand_orientation = median(_orientation_deviation(mask, item) for item in hand)
    group_baseline = median(item[1] + item[3] for item in group)
    group_aspect = median(item[3] / item[2] for item in group)
    group_orientation = median(_orientation_deviation(mask, item) for item in group)
    nearest_gap = min(
        max(0, hand_box[0] - (group_box[0] + group_box[2]), group_box[0] - (hand_box[0] + hand_box[2]))
        for hand_box in hand for group_box in group
    )
    separated = nearest_gap >= typical_width * 0.35
    baseline_deviation = abs(group_baseline - hand_baseline) >= median(item[3] for item in hand) * 0.08
    aspect_deviation = abs(group_aspect - hand_aspect) >= 0.075
    orientation_deviation = abs(group_orientation - hand_orientation) >= 8.0
    return separated and (baseline_deviation or aspect_deviation or orientation_deviation)


def _recover_stacked_meld_faces(
    group: list[tuple[int, int, int, int]], typical_width: float
) -> list[tuple[int, int, int, int]]:
    """Recover the lower face hidden by a stable 3+1 stacked meld layout.

    In the observed UI, the upper face and the middle lower face can become a
    single bright connected component.  The visible signature is relational:
    three adjacent components share a bottom baseline, the first two have the
    same raised top, and the third exposes the normal lower-face height.  One
    overlapping lower-face candidate is reconstructed from that local scale.
    """
    ordered = sorted(group)
    recovered: list[tuple[int, int, int, int]] = []
    for first, middle, last in zip(ordered, ordered[1:], ordered[2:]):
        heights = (first[3], middle[3], last[3])
        bottoms = (first[1] + first[3], middle[1] + middle[3], last[1] + last[3])
        if max(bottoms) - min(bottoms) > last[3] * 0.10:
            continue
        if abs(first[1] - middle[1]) > last[3] * 0.10:
            continue
        if min(first[3], middle[3]) < last[3] * 1.15:
            continue
        if last[1] - middle[1] < last[3] * 0.15:
            continue
        first_gap = middle[0] - (first[0] + first[2])
        second_gap = last[0] - (middle[0] + middle[2])
        if abs(first_gap) > typical_width * 0.20 or abs(second_gap) > typical_width * 0.20:
            continue
        width = int(round(typical_width))
        centre = middle[0] + middle[2] / 2
        candidate = (int(round(centre - width / 2)), last[1], width, last[3])
        if candidate not in recovered:
            recovered.append(candidate)
        break
    return recovered


def _recover_gap_meld_faces(
    group: list[tuple[int, int, int, int]], typical_width: float
) -> list[tuple[int, int, int, int]]:
    """Recover a dark meld face bracketed by two aligned visible faces."""
    ordered = sorted(group)
    recovered: list[tuple[int, int, int, int]] = []
    for left, right in zip(ordered, ordered[1:]):
        gap_start = left[0] + left[2]
        gap = right[0] - gap_start
        typical_height = median((left[3], right[3]))
        baseline_delta = abs((left[1] + left[3]) - (right[1] + right[3]))
        if not typical_width * 0.55 <= gap <= typical_width * 0.90:
            continue
        if baseline_delta > typical_height * 0.15:
            continue
        width = int(round(min(typical_width, gap * 1.10)))
        centre = gap_start + gap / 2
        y = int(round(median((left[1], right[1]))))
        height = int(round(typical_height))
        recovered.append((int(round(centre - width / 2)), y, width, height))
    return recovered


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


def _gold_is_draw_visual(
    gold: tuple[int, int, int, int] | None,
    all_boxes: list[tuple[int, int, int, int]],
) -> bool:
    """Distinguish a yellow drawn tile from the separate public Gold display.

    The decision is relational: a yellow tile face is ``draw_visual`` only
    when it is the isolated component immediately to the right of a dominant
    concealed-hand cluster with a compatible baseline.  No fixed coordinate
    or tile identity is used.
    """
    if gold is None:
        return False
    gold_boxes = [box for box in all_boxes if _overlaps(box, gold)]
    non_gold = [box for box in all_boxes if box not in gold_boxes]
    if not gold_boxes or not non_gold:
        return False
    typical_width = median(box[2] for box in non_gold)
    clusters = _clusters(non_gold, typical_width, gap_limit=0.32)
    hand = max(clusters, key=len, default=[])
    if len(hand) < 8:
        return False
    right_edge = max(box[0] + box[2] for box in hand)
    hand_baseline = median(box[1] + box[3] for box in hand)
    hand_height = median(box[3] for box in hand)
    for candidate in gold_boxes:
        gap = candidate[0] - right_edge
        baseline_delta = abs((candidate[1] + candidate[3]) - hand_baseline)
        if gap > typical_width * 0.55 and baseline_delta <= hand_height * 0.35:
            return True
    return False


def detect_dynamic_geometry(image: Image.Image, *, frame: str | int | None = None,
                            session: str | None = None) -> GeometryFrame:
    """Observe hand/draw_visual/gold/meld candidates without a fixed layout or count."""
    array = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    height, width = array.shape[:2]
    value = cv2.cvtColor(array, cv2.COLOR_BGR2HSV)[:, :, 2]
    bright_mask = (value > 150).astype(np.uint8) * 255
    gold = _gold_box(array)
    all_boxes = _bright_boxes(array)
    if _gold_is_draw_visual(gold, all_boxes):
        gold = None
    boxes = [box for box in all_boxes if gold is None or not _overlaps(box, gold)]
    widths = [box[2] for box in boxes]
    typical_width = median(widths) if widths else 0.0

    # The largest near-contiguous group establishes a local concealed-hand
    # reference.  This is resolution-normalized geometry, not a fixed x range
    # or a preselected hand count.
    clusters = _clusters(boxes, typical_width, gap_limit=0.32) if typical_width else []
    hand = max(clusters, key=len, default=[])
    hand_set = set(hand)
    right_edge = max((box[0] + box[2] for box in hand), default=-1)
    draw = None
    for candidate in boxes:
        if candidate in hand_set or candidate[0] < right_edge:
            continue
        gap = candidate[0] - right_edge
        baseline_delta = abs((candidate[1] + candidate[3]) - median(item[1] + item[3] for item in hand)) if hand else 0
        if gap > typical_width * 0.55 and baseline_delta <= median(item[3] for item in hand) * 0.35:
            draw = candidate
            break

    remainder = [box for box in boxes if box not in hand_set and box != draw]
    meld = []
    stacked_recovered = []
    gap_recovered = []
    # A meld may have more relaxed within-group spacing than the concealed
    # hand, but must remain a small, separated, geometrically deviant group.
    for group in _clusters(remainder, typical_width, gap_limit=1.10) if typical_width else []:
        if _meld_like_group(group, hand, bright_mask, typical_width):
            meld.extend(group)
            stacked_recovered.extend(_recover_stacked_meld_faces(group, typical_width))
            gap_recovered.extend(_recover_gap_meld_faces(group, typical_width))
    recovered_meld = [*stacked_recovered, *gap_recovered]
    if recovered_meld:
        boxes.extend(recovered_meld)
        meld.extend(recovered_meld)
    meld_set = set(meld)
    unknown = [box for box in remainder if box not in meld_set]

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
    if meld:
        issues.append("meld_candidates_detected")
    if stacked_recovered:
        issues.append("stacked_meld_overlap_recovered")
    if gap_recovered:
        issues.append("dark_meld_gap_recovered")
    # A missing yellow Gold candidate and a separately reported meld candidate
    # must never be merged into hand.  Neither invalidates an otherwise stable
    # geometry observation; occlusion/fragmentation and implausible hand counts
    # remain fatal.
    untrusted = any(
        issue not in {
            "gold_unreadable", "meld_candidates_detected",
            "stacked_meld_overlap_recovered", "dark_meld_gap_recovered",
        }
        for issue in issues
    )
    components = []
    for box in boxes:
        if box in hand_set:
            region, confidence = "hand", (0.92 if not untrusted else 0.60)
        elif box == draw:
            region, confidence = "draw_visual", (0.88 if not untrusted else 0.58)
        elif box in meld_set:
            region, confidence = "meld", 0.76 if not untrusted else 0.55
        else:
            region, confidence = "unknown", 0.45
        components.append(GeometryComponent(box, _normalized(box, width, height), region, confidence, frame, session))
    if gold is not None:
        components.append(GeometryComponent(gold, _normalized(gold, width, height), "gold", 0.90, frame, session))
    components.sort(key=lambda item: item.pixel_bbox[0])
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
