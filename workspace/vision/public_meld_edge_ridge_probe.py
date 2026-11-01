"""Offline own-pixel bevel-ridge geometry; never extrapolate a neighbor plane.

A broad bright ridge above a broad darker lower wall can support the bottom
boundary of an otherwise shaded face. This is a revealed geometry experiment,
not a semantic glyph detector or a calibrated Runtime identity observer.
"""
from __future__ import annotations
import math
from workspace.vision.evaluate_sift_symmetric_geometry_probe import normalize_single_face


def _runs(indices):
    groups = []
    for value in indices:
        if not groups or value != groups[-1][-1]+1:
            groups.append([value])
        else:
            groups[-1].append(value)
    return groups


def prepare_edge_ridge_band(image):
    import cv2
    import numpy as np
    audit = dict(development_only=True, runtime_integration=False,
        tile_identity="UNKNOWN", safe_for_runtime=False, safe_for_hint=False,
        safe_for_executor=False, raw_feature_fallback=False,
        body_mask_saturation_max=105, body_mask_value_min=115,
        minimum_brightness_contrast=20, minimum_row_body_width_fraction=0.7,
        vertical_context_canonical_pixels=2, neighbor_plane_extrapolated=False)
    def abstain(reason):
        return None, dict(audit, failed=True, reason=reason)
    if min(image.size) < 8:
        return abstain("insufficient_ridge_body")
    hsv = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2HSV)
    saturation, value = hsv[:, :, 1], hsv[:, :, 2]
    gray = saturation < 105
    body = gray & (value > 115)
    ys, xs = np.nonzero(body)
    if len(xs) < 40:
        return abstain("insufficient_ridge_body")
    body_width = int(xs.max()-xs.min()+1)
    row_body = body.sum(axis=1)
    eligible = row_body >= 0.7*body_width
    medians = np.full(image.height, np.nan)
    for y in np.flatnonzero(eligible):
        medians[y] = np.median(value[y][body[y]])
    if eligible.sum() < 10:
        return abstain("insufficient_broad_body_rows")
    baseline = float(np.nanmedian(medians))
    bright = body & (value >= baseline+20)
    broad_ridge_rows = np.flatnonzero(eligible & (medians >= baseline+20)
        & (bright.sum(axis=1) >= 0.7*body_width))
    runs = _runs(broad_ridge_rows.tolist())
    audit.update(body_width=body_width, broad_body_rows=int(eligible.sum()),
        body_row_median_baseline=baseline, broad_ridge_runs=runs,
        maximum_broad_row_median=float(np.nanmax(medians)))
    if len(runs) != 1:
        return abstain("no_unique_broad_ridge")
    ridge = runs[0]
    context = max(1, math.ceil(2*image.height/96))
    # A ridge without a substantial face above it is not a supported bottom.
    upper = np.flatnonzero(eligible & (np.arange(image.height) < ridge[0]))
    if len(upper) < 10 or float(np.median(medians[upper])) > baseline:
        return abstain("no_dimmer_broad_surface_above_ridge")
    ridge_value = float(np.median(medians[ridge]))
    gray_width = gray.sum(axis=1)
    darker = []
    for y in range(ridge[-1]+1, image.height):
        if gray_width[y] >= 0.7*body_width:
            lower_value = float(np.median(value[y][gray[y]]))
            if ridge_value-lower_value >= 20 and baseline-lower_value >= 20:
                darker.append(y)
    lower_runs = [r for r in _runs(darker) if len(r) >= context]
    if len(lower_runs) != 1:
        return abstain("no_unique_broad_darker_wall")
    lower = lower_runs[0]
    broad_gray = np.flatnonzero(gray_width >= 0.7*body_width)
    if lower[-1] != int(broad_gray[-1]):
        return abstain("darker_stripe_is_not_terminal_wall")
    # Do not skip a gap/animation or attach an unrelated distant background.
    if lower[0]-ridge[-1] > context+1:
        return abstain("darker_wall_not_adjacent_to_ridge")
    boundary = ridge[-1]+1+context
    normalized, mapping = normalize_single_face(image)
    audit.update(ridge_median=ridge_value, lower_wall_run=lower,
                 raw_boundary_with_context=boundary, normalization=mapping)
    if normalized is None or mapping["rotation_degrees"] != 0:
        return abstain("ridge_source_mapping_unavailable")
    _, top, _, height = mapping["tight_bbox"]
    bottom = min(normalized.height, math.floor((boundary-top)*normalized.height/height))
    if bottom < 8:
        return abstain("insufficient_ridge_surface")
    box = (0, 0, normalized.width, bottom)
    return normalized.crop(box), dict(audit, failed=False, reason="own_pixel_ridge_candidate",
        normalized_front_band_bbox=list(box), full_face_plane_rectification=False)
