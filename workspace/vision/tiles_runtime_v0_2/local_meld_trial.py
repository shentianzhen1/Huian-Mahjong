"""Explicit read-only trial adapter for local dark exposed-face recovery.

Baseline hand/Gold boxes and source pixels are preserved. This is not the
strict/default detector and does not classify exposed tile identities.
"""
from functools import partial


def detect_local_meld_trial(image, *, frame=None, session=None, edge_seams=True):
    import cv2
    import numpy as np
    from dataclasses import replace
    from .dynamic_geometry import detect_dynamic_geometry, _bright_boxes, _normalized, GeometryComponent
    from .local_dark_meld_probe import propose_local_meld_components
    baseline = detect_dynamic_geometry(image, frame=frame, session=session, edge_seams=edge_seams)
    if baseline.geometry_untrusted or not any(c.region_candidate == 'meld' for c in baseline.components):
        return baseline
    # _bright_boxes reads HSV value only. Adding20 with saturation changes its
    # >150 mask to the original image's >130 mask, without a global monkeypatch
    # or any change to the original pixels later used for classification.
    pixels = cv2.cvtColor(np.asarray(image.convert('RGB')), cv2.COLOR_RGB2BGR)
    proposal_pixels = np.minimum(pixels.astype(np.uint16) + 20, 255).astype(np.uint8)
    proposals = [dict(pixel_bbox=box, normalized_bbox=_normalized(box, *image.size),
                      region_candidate='unknown', frame=frame, session=session)
                 for box in _bright_boxes(proposal_pixels, edge_seams=edge_seams)]
    original = [c.to_dict() for c in baseline.components]
    recovered = propose_local_meld_components(original, proposals)
    if recovered is original:
        return baseline
    additions = tuple(GeometryComponent(tuple(c['pixel_bbox']), tuple(c['normalized_bbox']),
                      'meld', .76, frame, session, False) for c in recovered[len(original):])
    return replace(baseline, components=(*baseline.components, *additions))


def with_local_meld_trial(resources):
    return {**resources,
            'geometry_detector': partial(detect_local_meld_trial, edge_seams=True),
            'experimental_local_meld_geometry': True}
