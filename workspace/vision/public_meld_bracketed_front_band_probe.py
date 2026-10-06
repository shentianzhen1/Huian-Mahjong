"""Offline face-plane bounds supported by two same-group visible neighbors.

Caller must supply verified crops from the same source frame and reviewed row.
This probe does not detect a row, infer tile identity, or create a new source.
"""
from __future__ import annotations

import math
from workspace.vision.public_meld_front_band_probe import prepare_front_band
from workspace.vision.evaluate_sift_symmetric_geometry_probe import normalize_single_face


def _valid_bounds(image, bounds):
    if len(bounds) != 4 or any(isinstance(v, bool) or not isinstance(v, int) for v in bounds):
        raise ValueError("integer source xyxy required")
    x0, y0, x1, y1 = bounds
    if min(x0, y0) < 0 or x1 <= x0 or y1 <= y0 or image.size != (x1-x0, y1-y0):
        raise ValueError("source bounds do not match crop dimensions")


def prepare_bracketed_front_band(image, bounds, peers):
    """Use a direct band or a bracketed source-coordinate plane bound.

    No edge extrapolation, synthetic corners, raw feature fallback or label
    input. Peers must each independently pass the unchanged brightness probe.
    A normalized crop entirely above their evidenced boundary may be retained
    in full; that is external geometry support, not a failed-band raw fallback.
    """
    _valid_bounds(image, bounds)
    direct, original = prepare_front_band(image, merge_overlaps=True)
    audit = dict(development_only=True, runtime_integration=False,
                 tile_identity="UNKNOWN", safe_for_runtime=False,
                 safe_for_hint=False, safe_for_executor=False,
                 raw_feature_fallback=False, peer_pixels_are_independent_sources=False,
                 direct_preparation=original)
    if direct is not None:
        return direct, dict(audit, failed=False, reason="direct_front_band")
    normalized, normalization = normalize_single_face(image)
    if normalized is None or normalization["rotation_degrees"] != 0:
        return None, dict(audit, failed=True, reason="target_source_mapping_unavailable")
    tx0, ty0, tx1, ty1 = bounds
    eligible = []
    for peer_image, peer_bounds in peers:
        _valid_bounds(peer_image, peer_bounds)
        candidate, preparation = prepare_front_band(peer_image, merge_overlaps=True)
        mapping = preparation["normalization"]
        if candidate is None or mapping["rotation_degrees"] != 0:
            continue
        px0, py0, px1, py1 = peer_bounds
        # This helper handles a level, same-height row only. No inferred scale
        # or perspective model is smuggled into source-coordinate transfer.
        if py0 != ty0 or py1 != ty1:
            continue
        left, top, width, height = mapping["tight_bbox"]
        band_bottom = preparation["band"]["front_band_bbox"][3]
        eligible.append(dict(bounds=list(peer_bounds), center=(px0+px1)/2,
            top=py0+top, bottom=py0+top+band_bottom*height/mapping["output_size"][1],
            preparation=preparation))
    left = [p for p in eligible if p["center"] < tx0]
    right = [p for p in eligible if p["center"] > tx1]
    if len(left) != 1 or len(right) != 1:
        return None, dict(audit, failed=True, reason="no_unique_left_right_bracket",
                          eligible_peer_count=len(eligible))
    a, b = left[0], right[0]
    # Require adjacent peers; a distant unrelated group cannot bracket a face.
    if a["bounds"][2] < tx0 or b["bounds"][0] > tx1:
        return None, dict(audit, failed=True, reason="nonadjacent_peer_bounds")
    def interpolate(x, key):
        return a[key]+(b[key]-a[key])*(x-a["center"])/(b["center"]-a["center"])
    local_x, local_y, local_width, local_height = normalization["tight_bbox"]
    source_top = ty0+local_y
    shared_top = max(interpolate(tx0, "top"), interpolate(tx1, "top"))
    shared_bottom = min(interpolate(tx0, "bottom"), interpolate(tx1, "bottom"))
    context = 2*local_height/normalized.height
    audit.update(peer_evidence=[a, b], shared_source_top=shared_top,
                 shared_source_bottom=shared_bottom, target_normalization=normalization)
    if source_top < shared_top-context or shared_bottom <= source_top:
        return None, dict(audit, failed=True, reason="target_outside_bracketed_surface")
    if abs(a["bottom"]-b["bottom"]) > context:
        return None, dict(audit, failed=True, reason="peer_boundary_slope_requires_rectification")
    bottom = min(normalized.height, math.floor((shared_bottom-source_top)*normalized.height/local_height))
    if bottom < 8:
        return None, dict(audit, failed=True, reason="insufficient_bracketed_surface")
    box = (0, 0, normalized.width, bottom)
    return normalized.crop(box), dict(audit, failed=False,
        reason="bracketed_geometry_candidate", normalized_front_band_bbox=list(box),
        available_normalized_body_entirely_in_front_plane=bottom == normalized.height)



def image_geometry_key(image):
    """Identify identical input pixels; a digest alone cannot qualify identity."""
    import hashlib
    return (image.size, hashlib.sha256(image.convert("RGB").tobytes()).hexdigest())


def build_peer_contexts(groups):
    """Bind pixels to one exact verified source/frame/row, never choose by label."""
    contexts = {}
    for group in groups:
        if len(group) != 3 or len({(m["source_sha256"], m["source_frame_pin"], m["original_match_group"]) for m, _ in group}) != 1:
            raise ValueError("peers require a complete same-source/frame/match row")
        for index, (meta, image) in enumerate(group):
            contexts.setdefault(image_geometry_key(image), []).append((meta, image,
                [(m, im) for j, (m, im) in enumerate(group) if j != index]))
    return contexts


def prepare_from_peer_context(image, contexts, *, query_id=None, source_sha256=None):
    entries = [entry for entry in contexts.get(image_geometry_key(image), [])
               if entry[0]["query_id"] == query_id and entry[0]["source_sha256"] == source_sha256]
    if len(entries) != 1:
        result, audit = prepare_front_band(image, merge_overlaps=True)
        return result, dict(audit, peer_context_status="missing_or_ambiguous",
                            matched_context_count=len(entries))
    meta, _, peers = entries[0]
    result, audit = prepare_bracketed_front_band(image, meta["bounds"],
        [(im, m["bounds"]) for m, im in peers])
    return result, dict(audit, verified_source_sha256=meta["source_sha256"],
        verified_source_frame_pin=meta["source_frame_pin"],
        verified_original_match_group=meta["original_match_group"],
        peer_query_ids=[m["query_id"] for m, _ in peers])
