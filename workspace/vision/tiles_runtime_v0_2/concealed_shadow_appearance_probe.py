"""Development-only detector for the concealed-row bottom-shadow UI state.

A reviewed real match shows a strong gray horizontal band across the bottom of
every concealed tile during one UI state.  The ordinary template classifier
should not be changed merely from this one revealed match.  This helper makes
the appearance state explicit and reproducible so a separate shadow-normalized
identity bank can be evaluated without lowering the 0.82 Runtime threshold.
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
    """Candidate geometry for a parallel shadow-only identity bank.

    Apply to BOTH shadow queries and reviewed base templates.  Do not compare a
    trimmed query against the ordinary untrimmed bank.  This candidate remains
    offline until source-disjoint whole-hand validation exists.
    """
    normalized = _normalize_tile_face(image.convert("RGB"))
    width, height = normalized.size
    top = int(round(height * SHADOW_TEMPLATE_TOP_TRIM))
    bottom = int(round(height * (1.0 - SHADOW_TEMPLATE_BOTTOM_TRIM)))
    if bottom - top >= 12:
        normalized = normalized.crop((0, top, width, bottom))
    return normalized


def probe_image(path: str | Path) -> dict[str, object]:
    path = Path(path)
    if not path.is_file():
        raise ValueError("path must be an existing tile crop")
    with Image.open(path) as source:
        delta = bottom_shadow_delta(source)
    return {
        "schema_version": "concealed_shadow_appearance_probe_v0_1",
        "development_only": True,
        "runtime_changed": False,
        "threshold": DEVELOPMENT_SHADOW_DELTA_THRESHOLD,
        "bottom_minus_middle_delta": delta,
        "shadow_candidate": delta <= DEVELOPMENT_SHADOW_DELTA_THRESHOLD,
        "recommended_next_experiment": (
            "If shadow_candidate is true, compare a parallel shadow-normalized "
            "template bank using the same 0.82 acceptance threshold."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    args = parser.parse_args()
    print(json.dumps(probe_image(args.image), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
