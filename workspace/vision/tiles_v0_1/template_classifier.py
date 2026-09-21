"""Small offline template classifier used only to validate the labelled-data loop."""
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .labels import approved_labels
from .postprocess import TilePrediction


def _canonical_region(region):
    return "draw_visual" if region == "draw_region" else region


def _tile_face_box(image, brightness_threshold=100):
    """Return the dominant plausible bright tile-face box, or None.

    Empty slots are mostly dark table/UI pixels. Real Huian mini-program tile
    faces form a large bright connected component. The same geometry gate is
    used both for normalization and slot-presence detection so inference does
    not invent a tile for an empty draw/hand slot.
    """
    rgb = np.asarray(image.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    mask = (gray > brightness_threshold).astype(np.uint8) * 255
    mask = cv2.morphologyEx(
        mask, cv2.MORPH_CLOSE, np.ones((3, 3), dtype=np.uint8)
    )
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    if count <= 1:
        return None

    index = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, width, height, area = (
        int(value) for value in stats[index]
    )
    minimum_area = 0.25 * rgb.shape[0] * rgb.shape[1]
    if area < minimum_area or width < 8 or height < 12:
        return None
    return x, y, width, height


def _normalize_tile_face(image, brightness_threshold=100):
    """Crop the dominant bright tile face before template comparison."""
    rgb = np.asarray(image.convert("RGB"))
    box = _tile_face_box(image, brightness_threshold=brightness_threshold)
    if box is None:
        return image.convert("RGB")
    x, y, width, height = box
    return Image.fromarray(rgb[y:y + height, x:x + width])


def _normalize_gold_face(image):
    """Normalize the Huian gold skin while preserving the base tile face.

    In the target room the gold tile is the original face with a yellow/gold
    skin plus a small top-right "金" badge. The skin changes borders/background
    much more than the underlying tile glyph. Trim the skin-heavy outer rim and
    suppress the badge area before template comparison.
    """
    image = image.convert("RGB")
    width, height = image.size
    left = int(round(width * 0.06))
    top = int(round(height * 0.04))
    right = int(round(width * 0.94))
    bottom = int(round(height * 0.94))
    if right - left >= 8 and bottom - top >= 12:
        image = image.crop((left, top, right, bottom))
    return image


def _feature(image, region=None):
    if region == "gold_region":
        normalized = _normalize_gold_face(image)
    else:
        normalized = _normalize_tile_face(image)
    rgb = np.asarray(normalized.convert("RGB").resize((48, 72)))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    if region == "gold_region":
        # The gold badge is UI decoration, not part of the underlying tile ID.
        fill = int(np.median(gray[20:36, 34:48]))
        gray[:20, 34:48] = fill
    return cv2.equalizeHist(gray)


@dataclass(frozen=True)
class Classification:
    tile_id: str
    confidence: float


class TemplateTileClassifier:
    """NCC matching over reviewed label crops; intentionally not a trained model."""

    def __init__(self, templates, regional_templates=None):
        self.templates = {
            tile_id: tuple(values) for tile_id, values in templates.items()
        }
        self.regional_templates = {
            region: {
                tile_id: tuple(values)
                for tile_id, values in region_templates.items()
            }
            for region, region_templates in (regional_templates or {}).items()
        }
        if not self.templates:
            raise ValueError("No approved tile labels are available for offline inference")

    @classmethod
    def from_labels(cls, dataset_root, labels):
        root = Path(dataset_root)
        templates = {}
        regional_templates = {}
        for label in labels:
            image_path = root / label["image"]
            if not image_path.exists():
                continue
            with Image.open(image_path) as source:
                x, y, width, height = label["bbox"]
                # Runtime V0.2 stores privacy-reviewed tile-only assets under
                # templates/, while bbox remains the traceable coordinate in
                # the private source frame. Such assets are already cropped.
                is_runtime_crop = Path(label["image"]).parts[:1] == ("templates",)
                if is_runtime_crop:
                    crop = source.convert("RGB")
                else:
                    if x + width > source.width or y + height > source.height:
                        continue
                    crop = source.convert("RGB").crop((x, y, x + width, y + height))
            region = _canonical_region(label["region"])
            value = _feature(crop, region=region)
            templates.setdefault(label["tile_id"], []).append(value)
            regional_templates.setdefault(
                region, {}
            ).setdefault(label["tile_id"], []).append(value)
        return cls(templates, regional_templates)

    @classmethod
    def from_dataset(cls, dataset_root):
        root = Path(dataset_root)
        return cls.from_labels(root, approved_labels(root))

    def classify(self, image, region=None):
        region = _canonical_region(region)
        sample = _feature(image, region=region)
        templates = (
            self.regional_templates.get(region, {})
            if region is not None else self.templates
        )
        if not templates:
            raise ValueError(f"No approved templates are available for {region}")
        best_tile, best_score = None, float("-inf")
        for tile_id, examples in templates.items():
            score = max(float(cv2.matchTemplate(
                sample, template, cv2.TM_CCOEFF_NORMED
            )[0, 0]) for template in examples)
            if not np.isfinite(score):
                score = -1.0
            if score > best_score:
                best_tile, best_score = tile_id, score
        return Classification(best_tile, max(0.0, best_score))

    def classify_slots(self, image, profile, region):
        if profile.region_mode(region) != "tile":
            return ()
        if not profile.slots.get(region):
            raise ValueError(f"No calibrated tile slots for {region}")
        x, y, _, _ = profile.regions[region]
        region_image = profile.crop(image, region)
        results = []
        for slot, (local_x, local_y, width, height) in enumerate(profile.slots[region]):
            crop = region_image.crop((local_x, local_y,
                                      local_x + width, local_y + height))
            if _tile_face_box(crop) is None:
                continue
            result = self.classify(crop, region=region)
            results.append(TilePrediction(
                result.tile_id, result.confidence, region,
                (x + local_x, y + local_y, width, height), slot
            ))
        return tuple(results)
