"""Development-only table-background contour probe; no identity inputs."""
from __future__ import annotations


def outer_body_box(image, detector_bbox):
    """Return an unclipped foreground envelope, or abstain.

    The median of a search-window rim estimates the table colour. This assumes
    a flat bottom meld on a locally uniform table, not arbitrary screenshots.
    """
    import cv2
    import numpy as np

    x, y, w, h = detector_bbox
    px, py = max(3, round(w * .1)), max(3, round(h * .1))
    left, top = max(0, x-px), max(0, y-py)
    right, bottom = min(image.width, x+w+px), min(image.height, y+h+py)
    rgb = np.asarray(image.crop((left, top, right, bottom))).astype(np.float32)
    rim = np.concatenate((rgb[:3].reshape(-1, 3), rgb[-3:].reshape(-1, 3),
                          rgb[:, :3].reshape(-1, 3), rgb[:, -3:].reshape(-1, 3)))
    background = np.median(rim, axis=0)
    mask = (np.linalg.norm(rgb-background, axis=2) > 30).astype(np.uint8)*255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    eligible = []
    for contour in contours:
        cx, cy, cw, ch = cv2.boundingRect(contour)
        gx, gy = left+cx, top+cy
        overlap = max(0, min(gx+cw, x+w)-max(gx, x))*max(0, min(gy+ch, y+h)-max(gy, y))
        if overlap > .4*w*h:
            eligible.append((cv2.contourArea(contour), (cx, cy, cw, ch)))
    audit = {'search_xyxy': [left, top, right, bottom],
             'background_rgb': background.tolist(), 'distance_threshold': 30,
             'search_padding_fraction': .1, 'eligible_contours': len(eligible)}
    if len(eligible) != 1:
        return None, {**audit, 'reason': 'ambiguous_or_absent_body'}
    _, (cx, cy, cw, ch) = eligible[0]
    if cx == 0 or cy == 0 or cx+cw == right-left or cy+ch == bottom-top:
        return None, {**audit, 'reason': 'body_touches_search_boundary'}
    box = (left+cx, top+cy, left+cx+cw, top+cy+ch)
    return box, {**audit, 'outer_body_xyxy': list(box)}
