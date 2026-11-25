"""Offline vertical front-band probe; not full face-plane rectification.

Apply only to an already split/normalized single face. X and the top boundary
are preserved. An adaptive brightness split may remove a darker lower side
wall, but is not a semantic glyph detector or a calibrated Runtime observer.
"""
from __future__ import annotations


def prepare_front_band(image, *, merge_overlaps=False):
    """Same strict feature preparation for references/queries, no raw fallback."""
    from workspace.vision.evaluate_sift_symmetric_geometry_probe import normalize_single_face
    normalized, normalization = normalize_single_face(image)
    if normalized is None:
        return None, dict(failed=True, reason="normalization_abstained", normalization=normalization)
    box, audit = front_band_bbox(normalized, merge_overlaps=merge_overlaps)
    if box is None:
        return None, dict(failed=True, reason="front_band_abstained", normalization=normalization, band=audit)
    return normalized.crop(box), dict(failed=False, normalization=normalization, band=audit)


def merge_overlapping_boxes(boxes):
    """Union strictly overlapping component envelopes; never bridge a gap."""
    remaining = [tuple(box) for box in boxes]
    result = []
    while remaining:
        group = [remaining.pop(0)]
        cursor = 0
        while cursor < len(group):
            a = group[cursor]
            connected = []
            for b in remaining:
                if (max(a[0], b[0]) < min(a[0]+a[2], b[0]+b[2])
                        and max(a[1], b[1]) < min(a[1]+a[3], b[1]+b[3])):
                    connected.append(b)
            for b in connected:
                remaining.remove(b)
                group.append(b)
            cursor += 1
        left = min(b[0] for b in group)
        top = min(b[1] for b in group)
        right = max(b[0]+b[2] for b in group)
        bottom = max(b[1]+b[3] for b in group)
        result.append((left, top, right-left, bottom-top, sum(b[4] for b in group)))
    return result


def front_band_bbox(image, *, merge_overlaps=False):
    import cv2
    import numpy as np

    audit = dict(development_only=True, runtime_integration=False,
                 tile_identity="UNKNOWN", full_face_plane_rectification=False,
                 safe_for_runtime=False, safe_for_hint=False, safe_for_executor=False,
                 body_mask_saturation_max=105, body_mask_value_min=115,
                 minimum_cluster_median_contrast=20, closing_kernel=[3, 3],
                 minimum_component_body_width_fraction=0.7, vertical_context=2)
    audit["merge_overlapping_component_envelopes"] = merge_overlaps
    def abstain(reason):
        return None, dict(audit, reason=reason)
    if min(image.size) < 8:
        return abstain("insufficient_light_body")
    rgb = np.asarray(image.convert("RGB"))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    saturation, value = hsv[:, :, 1], hsv[:, :, 2]
    body = (saturation < 105) & (value > 115)
    if int(body.sum()) < 40:
        return abstain("insufficient_light_body")
    samples = value[body].reshape(-1, 1)
    cutoff, _ = cv2.threshold(samples, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    dim, light = samples[samples <= cutoff], samples[samples > cutoff]
    audit["adaptive_value_cutoff"] = float(cutoff)
    if len(dim) < 10 or len(light) < 10:
        return abstain("no_two_brightness_populations")
    contrast = float(np.median(light) - np.median(dim))
    audit["cluster_median_contrast"] = contrast
    if contrast < 20:
        return abstain("weak_brightness_separation")
    mask = ((body & (value > cutoff)).astype(np.uint8) * 255)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    ys, xs = np.nonzero(body)
    body_width = int(xs.max() - xs.min() + 1)
    candidates = []
    for x, y, width, height, area in stats[1:]:
        if width >= 0.7 * body_width and height >= 0.2 * image.height:
            candidates.append((int(x), int(y), int(width), int(height), int(area)))
    audit["eligible_bright_components_before_merge"] = len(candidates)
    if merge_overlaps:
        candidates = merge_overlapping_boxes(candidates)
    audit["eligible_bright_components"] = len(candidates)
    if len(candidates) != 1:
        return abstain("ambiguous_or_absent_front_component")
    x, y, width, height, area = candidates[0]
    boundary = y + height
    audit["bright_component_xywh"] = [x, y, width, height]
    # Require a lower dim band; a white face filling the crop has no supported
    # front/side boundary. Never silently guess a fixed-height cut.
    if boundary + 2 >= int(ys.max()) + 1:
        return abstain("no_lower_side_band")
    lower_body = body[boundary:, :]
    lower_values = value[boundary:, :][lower_body]
    if len(lower_values) < 10 or float(np.median(light) - np.median(lower_values)) < 20:
        return abstain("lower_band_not_darker")
    # Preserve both horizontal edges and ALL upper glyph pixels. This is a
    # vertical band, not a quadrilateral or a claim of pixel-exact boundaries.
    box = (0, 0, image.width, min(image.height, boundary + 2))
    audit.update(reason="development_front_band_candidate", front_band_bbox=list(box))
    return box, audit
