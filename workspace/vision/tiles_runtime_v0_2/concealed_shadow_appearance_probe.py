"""Development-only detector and identity candidates for concealed-row shadow UI.

A reviewed real match shows a strong gray horizontal band across the bottom of
every concealed tile during one UI state.  The ordinary template classifier
should not be changed merely from this one revealed match.  This helper makes
the appearance state explicit and exposes shadow-only feature candidates so
they can be evaluated without lowering the 0.82 Runtime threshold.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from workspace.vision.tiles_v0_1.template_classifier import _normalize_tile_face


# Development threshold chosen only to sit inside the large gap observed in the
# 2026-10-03 paired diagnostic: ordinary samples >= about -35, shadow samples
# <= about -67. It is NOT a promoted Runtime constant.
DEVELOPMENT_SHADOW_DELTA_THRESHOLD = -50.0
SIDE_FRACTION = 0.18
MIDDLE_BAND = (0.35, 0.55)
BOTTOM_BAND = (0.82, 1.00)
SHADOW_TEMPLATE_TOP_TRIM = 0.06
SHADOW_TEMPLATE_BOTTOM_TRIM = 0.20
GLYPH_X_MARGIN = 0.05
GLYPH_Y_START = 0.02
GLYPH_Y_END = 0.88
GLYPH_GRAY_THRESHOLD = 160
GLYPH_SATURATION_THRESHOLD = 40
GLYPH_FEATURE_SIZE = (48, 72)


def _side_background_median(gray: np.ndarray, y0: float, y1: float) -> float:
    height, width = gray.shape
    start = max(0, min(height - 1, int(round(height * y0))))
    stop = max(start + 1, min(height, int(round(height * y1))))
    band = gray[start:stop]
    side = max(1, int(round(width * SIDE_FRACTION)))
    pixels = np.concatenate((band[:, :side].ravel(), band[:, -side:].ravel()))
    return float(np.median(pixels))


def bottom_shadow_delta(image: Image.Image) -> float:
    """Return bottom-minus-middle side-background brightness after face crop."""
    normalized = _normalize_tile_face(image.convert("RGB"))
    gray = cv2.cvtColor(np.asarray(normalized), cv2.COLOR_RGB2GRAY)
    middle = _side_background_median(gray, *MIDDLE_BAND)
    bottom = _side_background_median(gray, *BOTTOM_BAND)
    return bottom - middle


def shadow_appearance_candidate(
    image: Image.Image,
    *,
    threshold: float = DEVELOPMENT_SHADOW_DELTA_THRESHOLD,
) -> bool:
    return bottom_shadow_delta(image) <= threshold


def shadow_template_normalize(image: Image.Image) -> Image.Image:
    """Simple crop candidate for a parallel shadow-only identity bank."""
    normalized = _normalize_tile_face(image.convert("RGB"))
    width, height = normalized.size
    top = int(round(height * SHADOW_TEMPLATE_TOP_TRIM))
    bottom = int(round(height * (1.0 - SHADOW_TEMPLATE_BOTTOM_TRIM)))
    if bottom - top >= 12:
        normalized = normalized.crop((0, top, width, bottom))
    return normalized


def shadow_glyph_mask_feature(image: Image.Image) -> np.ndarray:
    """Extract glyph/dot geometry while discarding the bottom-shadow background.

    This is deliberately a separate feature family, not a replacement for the
    production grayscale NCC feature.  It keeps the upper 88% of the normalized
    face, marks dark or chromatic glyph pixels, removes tiny/broad background
    fragments, then aspect-fits the surviving glyph mask to 48x72.

    On the revealed 40s->46s paired same-match diagnostic this representation
    reached 12/13 self-bank exact matches versus 6/13 for the current grayscale
    reproduction.  That is feasibility evidence only, not promotion evidence.
    """
    normalized = _normalize_tile_face(image.convert("RGB"))
    rgb = np.asarray(normalized)
    height, width = rgb.shape[:2]
    x0 = int(round(width * GLYPH_X_MARGIN))
    x1 = int(round(width * (1.0 - GLYPH_X_MARGIN)))
    y0 = int(round(height * GLYPH_Y_START))
    y1 = int(round(height * GLYPH_Y_END))
    if x1 - x0 < 8 or y1 - y0 < 12:
        working = rgb
    else:
        working = rgb[y0:y1, x0:x1]

    gray = cv2.cvtColor(working, cv2.COLOR_RGB2GRAY)
    hsv = cv2.cvtColor(working, cv2.COLOR_RGB2HSV)
    mask = (
        (gray < GLYPH_GRAY_THRESHOLD)
        | (hsv[:, :, 1] > GLYPH_SATURATION_THRESHOLD)
    ).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), dtype=np.uint8))

    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    kept = np.zeros_like(mask)
    work_h, work_w = mask.shape
    for index in range(1, count):
        x, y, component_w, component_h, area = (
            int(value) for value in stats[index]
        )
        # Keep plausible glyph pieces.  Very broad shallow components are UI
        # bands/borders rather than tile identity.
        if area < 8:
            continue
        if component_w >= int(round(work_w * 0.80)):
            continue
        if component_h >= int(round(work_h * 0.50)):
            continue
        kept[labels == index] = 255

    ys, xs = np.where(kept > 0)
    if xs.size >= 20:
        left = max(0, int(xs.min()) - 2)
        right = min(kept.shape[1], int(xs.max()) + 3)
        top = max(0, int(ys.min()) - 2)
        bottom = min(kept.shape[0], int(ys.max()) + 3)
        kept = kept[top:bottom, left:right]

    target_w, target_h = GLYPH_FEATURE_SIZE
    canvas = np.zeros((target_h, target_w), dtype=np.uint8)
    if kept.size == 0 or kept.shape[0] == 0 or kept.shape[1] == 0:
        return canvas
    scale = min(
        (target_w - 4) / max(1, kept.shape[1]),
        (target_h - 4) / max(1, kept.shape[0]),
    )
    resized_w = max(1, int(round(kept.shape[1] * scale)))
    resized_h = max(1, int(round(kept.shape[0] * scale)))
    resized = cv2.resize(
        kept, (resized_w, resized_h), interpolation=cv2.INTER_NEAREST
    )
    paste_x = (target_w - resized_w) // 2
    paste_y = (target_h - resized_h) // 2
    canvas[paste_y:paste_y + resized_h, paste_x:paste_x + resized_w] = resized
    return canvas


def probe_image(path: str | Path) -> dict[str, object]:
    path = Path(path)
    if not path.is_file():
        raise ValueError("path must be an existing tile crop")
    with Image.open(path) as source:
        delta = bottom_shadow_delta(source)
    return {
        "schema_version": "concealed_shadow_appearance_probe_v0_2",
        "development_only": True,
        "runtime_changed": False,
        "threshold": DEVELOPMENT_SHADOW_DELTA_THRESHOLD,
        "bottom_minus_middle_delta": delta,
        "shadow_candidate": delta <= DEVELOPMENT_SHADOW_DELTA_THRESHOLD,
        "candidate_features": [
            "shadow_template_normalize",
            "shadow_glyph_mask_feature",
        ],
        "recommended_next_experiment": (
            "If shadow_candidate is true, compare a parallel shadow-normalized "
            "and glyph-mask template bank on the same private crops while keeping "
            "the 0.82 Runtime identity threshold frozen."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    args = parser.parse_args()
    print(json.dumps(probe_image(args.image), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
