"""Development-only dark-face fallback for public meld front-band geometry.

The existing front_band_bbox() remains authoritative. This probe is permitted
only after that path abstains specifically because no unique broad bright
component exists. It never assigns tile identity/action and is not Runtime.
"""
from __future__ import annotations

ALLOWED_PRIMARY_REASON = "ambiguous_or_absent_front_component"


def dark_face_front_band_bbox(image, primary_audit, *, quantile=0.20):
    """Try relative-brightness geometry after one narrow primary abstention."""
    import cv2
    import numpy as np

    audit = dict(
        development_only=True, runtime_integration=False,
        tile_identity="UNKNOWN", safe_for_runtime=False,
        safe_for_hint=False, safe_for_executor=False,
        fallback_trigger_reason=primary_audit.get("reason"),
        relative_body_quantile=quantile,
        body_floor_clamp=[85, 115],
        minimum_cluster_median_contrast=20,
        minimum_component_body_width_fraction=0.7,
    )
    if primary_audit.get("reason") != ALLOWED_PRIMARY_REASON:
        return None, dict(audit, reason="fallback_not_permitted")

    rgb = np.asarray(image.convert("RGB"))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    saturation, value = hsv[:, :, 1], hsv[:, :, 2]
    low_saturation = saturation < 105
    values = value[low_saturation]
    if len(values) < 40:
        return None, dict(audit, reason="insufficient_body")
    floor = float(np.clip(np.percentile(values, quantile * 100.0), 85, 115))
    audit["relative_body_value_floor"] = floor
    body = low_saturation & (value > floor)
    if int(body.sum()) < 40:
        return None, dict(audit, reason="insufficient_body")

    samples = value[body].reshape(-1, 1)
    cutoff, _ = cv2.threshold(samples, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    dim, light = samples[samples <= cutoff], samples[samples > cutoff]
    audit["adaptive_value_cutoff"] = float(cutoff)
    if len(dim) < 10 or len(light) < 10:
        return None, dict(audit, reason="no_two_brightness_populations")
    contrast = float(np.median(light) - np.median(dim))
    audit["cluster_median_contrast"] = contrast
    if contrast < 20:
        return None, dict(audit, reason="weak_brightness_separation")

    mask = ((body & (value > cutoff)).astype(np.uint8) * 255)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    ys, xs = np.nonzero(body)
    body_width = int(xs.max() - xs.min() + 1)
    candidates = []
    for x, y, width, height, area in stats[1:]:
        if width >= 0.7 * body_width and height >= 0.2 * image.height:
            candidates.append((int(x), int(y), int(width), int(height), int(area)))
    audit["eligible_bright_components"] = len(candidates)
    if len(candidates) != 1:
        return None, dict(audit, reason="ambiguous_or_absent_front_component")

    x, y, width, height, _ = candidates[0]
    boundary = y + height
    audit["bright_component_xywh"] = [x, y, width, height]
    if boundary + 2 >= int(ys.max()) + 1:
        return None, dict(audit, reason="no_lower_side_band")
    lower_values = value[boundary:, :][body[boundary:, :]]
    if len(lower_values) < 10 or float(np.median(light) - np.median(lower_values)) < 20:
        return None, dict(audit, reason="lower_band_not_darker")
    box = (0, 0, image.width, min(image.height, boundary + 2))
    return box, dict(audit, reason="development_dark_face_front_band_candidate",
                     front_band_bbox=list(box))
