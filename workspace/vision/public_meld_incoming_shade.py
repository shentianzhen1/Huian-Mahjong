"""Development-only shading *appearance* on already-reviewed public meld faces.

The darkened slot MAY encode an acquired tile, but that relationship still
requires independently timed discard/action evidence. Geometry or a dark
slot is never proof of CHI/PENG/KONG, incoming tile identity, or actor.

This module never consumes tile labels and never promotes output to Runtime,
Hint or Executor. The gate was explored using existing, already-inspected
private recordings; its thresholds are not blind-tested/generalized.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from PIL import Image


# Eight-bit RGB maximum is HSV value.  These intentionally conservative
# development thresholds separate the strong face-wide overlays observed in
# already-reviewed footage from artwork-only or weak brightness variation.
_MAX_SHADED_V65 = 165.0
_MIN_UNSHADED_V65 = 178.0
_MIN_RELATIVE_GAP = 28.0
_MAX_PEER_SPREAD = 20.0


@dataclass(frozen=True)
class MeldShadeEvidence:
    shadow_index: int | None
    brightness_v65: tuple[float, ...]
    shadow_score: tuple[float, ...]
    darkness_gap: float | None
    reason: str

    def to_dict(self) -> dict:
        return {
            "schema_version": "public_meld_shade_appearance_development_v0_1",
            "development_only": True,
            "shadow_index": self.shadow_index,
            "brightness_v65": list(self.brightness_v65),
            # Per-face relative darkness in 8-bit V units, NOT probabilities.
            "shadow_score": list(self.shadow_score),
            "darkness_gap": self.darkness_gap,
            "reason": self.reason,
            "basis": "central_face_65th_percentile_rgb_max",
            "shade_is_confirmed_incoming_tile": False,
            "incoming_tile_id": "UNKNOWN",
            "actor": "UNKNOWN",
            "turn_actor": "UNKNOWN",
            "action_kind": "UNKNOWN",
            "requires_independent_discard_corroboration": True,
            "formal_promotion_evidence": False,
            "safe_for_runtime": False,
            "safe_for_executor": False,
        }


def _abstain(reason: str) -> MeldShadeEvidence:
    return MeldShadeEvidence(None, (), (), None, reason)


def _pale_face_brightness(face: Image.Image) -> float | None:
    """Artwork-robust bright-face statistic; ignore tile edge and 3D foot."""
    if not isinstance(face, Image.Image):
        return None
    if face.width < 20 or face.height < 32:
        return None
    rgb = np.asarray(face.convert("RGB"), dtype=np.uint8)
    h, w = rgb.shape[:2]
    top, bottom = round(h * 0.13), round(h * 0.82)
    left, right = round(w * 0.15), round(w * 0.85)
    if bottom - top < 12 or right - left < 10:
        return None
    interior = rgb[top:bottom, left:right]
    value = interior.max(axis=2)
    return round(float(np.percentile(value, 65)), 3)


def detect_reviewed_meld_shade(
    face_crops: Sequence[Image.Image],
    *,
    reviewed_meld_roi: bool,
    layout: str = "regular_three_face",
) -> MeldShadeEvidence:
    """Identify only a distinctly dim SLOT in a vetted horizontal 3-face ROI.

    The review flag is supplied by a caller that *already* verifies exact
    source video/screenshot and human-reviewed group geometry. Setting this
    flag does not make arbitrary pixels proof of a public meld: never call
    on global bottom_group candidates or the Gold/concealed hand region.
    """
    if not reviewed_meld_roi:
        return _abstain("unreviewed_or_non_meld_region")
    if layout != "regular_three_face" or len(face_crops) != 3:
        return _abstain("unsupported_meld_geometry")
    values = tuple(_pale_face_brightness(face) for face in face_crops)
    if any(value is None for value in values):
        return _abstain("invalid_or_too_small_face_crop")
    brightness = tuple(float(value) for value in values)
    scores = tuple(
        round(max(0.0, min(brightness[j] for j in range(3) if j != i) - value), 3)
        for i, value in enumerate(brightness)
    )
    darkest = min(range(3), key=lambda i: brightness[i])
    peers = [brightness[j] for j in range(3) if j != darkest]
    gap = round(min(peers) - brightness[darkest], 3)
    if (
        brightness[darkest] > _MAX_SHADED_V65
        or min(peers) < _MIN_UNSHADED_V65
        or gap < _MIN_RELATIVE_GAP
        or max(peers) - min(peers) > _MAX_PEER_SPREAD
    ):
        return MeldShadeEvidence(
            None, brightness, scores, gap,
            "ambiguous_or_no_unique_darkened_face",
        )
    return MeldShadeEvidence(
        darkest, brightness, scores, gap,
        "distinct_localized_darkened_face_appearance_only",
    )
