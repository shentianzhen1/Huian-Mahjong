"""Offline geometry probe for a leftmost upper meld missed by generic intake.

Derive a narrow body band from two existing upper-group peers, then recover
adjacent similarly sized components inside that band. This never modifies
the generic detector, assigns identity/action, or enables Runtime advice.
"""
from __future__ import annotations

from workspace.vision.public_tile_detector import (
    PublicGeometryCandidate,
    PublicGeometryFrame,
    _expand_top_group,
    _normalized,
)


def recover_top_row_peer_candidates(image, detection: PublicGeometryFrame):
    """Return supplemental development candidates or abstain without two peers."""
    import cv2
    import numpy as np

    peers = [c for c in detection.candidates if c.geometry_kind == "top_group"]
    if len(peers) < 2:
        return ()
    width, height = image.size
    padding = max(2, round(height * 0.006))
    top = max(c.pixel_bbox[1] + padding for c in peers)
    bottom = min(c.pixel_bbox[1] + c.pixel_bbox[3] - padding for c in peers)
    body_heights = [c.pixel_bbox[3] - 2 * padding for c in peers]
    if bottom <= top or bottom - top < 0.8 * max(body_heights):
        return ()
    body_widths = [c.pixel_bbox[2] - 2 * max(1, round(width * 0.0015)) for c in peers]
    reference_width = float(np.median(body_widths))
    rgb = np.asarray(image.convert("RGB"))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    mask = ((hsv[:, :, 1] < 105) & (hsv[:, :, 2] > 115)).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask[top:bottom], 8)
    result = []
    for left, local_top, box_width, box_height, area in stats[1:count]:
        left, local_top, box_width, box_height, area = map(
            int, (left, local_top, box_width, box_height, area)
        )
        if not (0.7 * reference_width <= box_width <= 1.3 * reference_width):
            continue
        if box_height < 0.8 * (bottom - top) or box_width / width > 0.085:
            continue
        if not (1.75 <= box_width / box_height <= 4.5):
            continue
        fill = area / (box_width * box_height)
        if fill < 0.18:
            continue
        right = left + box_width
        # Existing groups must never be duplicated by the supplemental path.
        if any(min(right, p.pixel_bbox[0] + p.pixel_bbox[2])
               - max(left, p.pixel_bbox[0]) > box_width * 0.5 for p in peers):
            continue
        gaps = [max(p.pixel_bbox[0] - right,
                    left - p.pixel_bbox[0] - p.pixel_bbox[2], 0) for p in peers]
        if min(gaps) > width * 0.012:
            continue
        bbox = _expand_top_group(
            (left, top + local_top, box_width, box_height), width, height
        )
        result.append(PublicGeometryCandidate(
            bbox, _normalized(bbox, width, height), "top_group",
            round(min(0.86, 0.58 + fill * 0.36), 6), round(fill, 6),
            detection.frame, detection.session,
        ))
    return tuple(result)
