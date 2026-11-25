"""Read-only, development-only ranking of template matches with provenance.

This does not apply identity gates, modify labels, or select/promote a classifier.
Private query and template images remain in the caller's private environment.
"""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from workspace.vision.tiles_v0_1.template_classifier import _feature


def rank_reviewed_templates(image, dataset_root, labels, *, region="concealed_identity", gold_skin=False):
    """Return the NCC ordering over existing ordinary concealed templates."""
    root = Path(dataset_root)
    feature_region = "gold_region" if gold_skin else region
    sample = _feature(image, region=feature_region)
    results = []
    for row in labels:
        if not gold_skin and (row.get("gold_skin_only") or row.get("region") not in {
            "hand_region", "draw_region", "draw_visual"
        }):
            continue
        path = root / row["image"]
        if not path.is_file():
            continue
        with Image.open(path) as source:
            crop = source.convert("RGB")
            if Path(row["image"]).parts[:1] != ("templates",):
                x, y, w, h = row["bbox"]
                if x + w > source.width or y + h > source.height:
                    continue
                crop = crop.crop((x, y, x + w, y + h))
        score = float(cv2.matchTemplate(sample, _feature(crop, region=feature_region),
                                       cv2.TM_CCOEFF_NORMED)[0, 0])
        if not np.isfinite(score):
            score = -1.0
        results.append({
            "tile_id": row["tile_id"], "score": score,
            "image": row["image"], "source_sha256": row.get("sha256"),
            "source_session": row.get("source_session"),
            "original_match_group": row.get("original_match_group", "UNKNOWN"),
        })
    return sorted(results, key=lambda item: item["score"], reverse=True)
