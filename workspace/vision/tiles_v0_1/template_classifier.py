"""Small offline template classifier used only to validate the labelled-data loop."""
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .labels import approved_labels
from .postprocess import TilePrediction


def _feature(image):
    rgb = np.asarray(image.convert("RGB").resize((48, 72)))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    return cv2.equalizeHist(gray)


@dataclass(frozen=True)
class Classification:
    tile_id: str
    confidence: float


class TemplateTileClassifier:
    """NCC matching over reviewed label crops; intentionally not a trained model."""

    def __init__(self, templates):
        self.templates = {tile_id: tuple(values) for tile_id, values in templates.items()}
        if not self.templates:
            raise ValueError("No approved tile labels are available for offline inference")

    @classmethod
    def from_dataset(cls, dataset_root):
        root = Path(dataset_root)
        templates = {}
        for label in approved_labels(root):
            image_path = root / label["image"]
            if not image_path.exists():
                continue
            with Image.open(image_path) as source:
                x, y, width, height = label["bbox"]
                if x + width > source.width or y + height > source.height:
                    continue
                crop = source.convert("RGB").crop((x, y, x + width, y + height))
            templates.setdefault(label["tile_id"], []).append(_feature(crop))
        return cls(templates)

    def classify(self, image):
        sample = _feature(image)
        best_tile, best_score = None, float("-inf")
        for tile_id, examples in self.templates.items():
            score = max(float(cv2.matchTemplate(
                sample, template, cv2.TM_CCOEFF_NORMED
            )[0, 0]) for template in examples)
            if not np.isfinite(score):
                score = -1.0
            if score > best_score:
                best_tile, best_score = tile_id, score
        return Classification(best_tile, max(0.0, best_score))

    def classify_slots(self, image, profile, region):
        if not profile.slots.get(region):
            raise ValueError(f"No calibrated tile slots for {region}")
        x, y, _, _ = profile.regions[region]
        region_image = profile.crop(image, region)
        results = []
        for slot, (local_x, local_y, width, height) in enumerate(profile.slots[region]):
            crop = region_image.crop((local_x, local_y,
                                      local_x + width, local_y + height))
            result = self.classify(crop)
            results.append(TilePrediction(
                result.tile_id, result.confidence, region,
                (x + local_x, y + local_y, width, height), slot
            ))
        return tuple(results)
