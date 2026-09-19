"""Experimental classifier for face-up gold-skinned Huian tiles.

Gold tiles keep the underlying tile artwork but add a gold/yellow skin and a
top-right 金 badge. V0.1 therefore avoids treating gold as a separate taxonomy:
it returns the normal tile_id plus is_gold=True.

This is an experimental bridge, not an Executor gate. It uses local-feature
matching against reviewed non-gold tile templates. Tong tiles get an additional
pip-count stage because the gold skin can make nearby tong numerals ambiguous.
"""
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .labels import approved_labels
from .taxonomy import category_for


def _crop_label(root, label):
    image_path = Path(root) / label["image"]
    with Image.open(image_path) as source:
        image = source.convert("RGB")
        x, y, width, height = label["bbox"]
        return image.crop((x, y, x + width, y + height))


def _sift_descriptor(image):
    rgb = np.asarray(image.convert("RGB"))
    enlarged = cv2.resize(
        rgb, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC
    )
    gray = cv2.cvtColor(enlarged, cv2.COLOR_RGB2GRAY)
    height, width = gray.shape
    mask = np.full_like(gray, 255)
    # The top-right 金 badge is an overlay rather than part of the base tile face.
    mask[: int(height * 0.35), int(width * 0.65):] = 0
    detector = cv2.SIFT_create(nfeatures=100)
    _, descriptor = detector.detectAndCompute(gray, mask)
    return descriptor


def _good_sift_matches(sample, template):
    if (
        sample is None
        or template is None
        or len(sample) < 2
        or len(template) < 2
    ):
        return 0
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    matches = matcher.knnMatch(sample, template, k=2)
    return sum(
        1 for first, second in matches
        if first.distance < 0.75 * second.distance
    )


def count_tong_pips(image):
    """Count visible tong pips after suppressing gold badge and frame.

    Returns 0 when no plausible circles are found. This is intentionally a
    narrow helper for P1..P9 and should not be used for other suits.

    The distance/accumulator thresholds are deliberately conservative. They were
    tightened after replay-temporal diagnostics showed compressed P4 frames could
    otherwise invent a fifth circle from badge/edge texture.
    """
    rgb = np.asarray(image.convert("RGB"))
    enlarged = cv2.resize(
        rgb, None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC
    )
    gray = cv2.cvtColor(enlarged, cv2.COLOR_RGB2GRAY)
    height, width = gray.shape
    fill = int(np.median(gray))

    gray[: int(height * 0.42), int(width * 0.55):] = fill
    gray[: int(height * 0.08), :] = fill
    gray[-int(height * 0.08):, :] = fill
    gray[:, : int(width * 0.08)] = fill
    gray[:, -int(width * 0.08):] = fill
    gray = cv2.GaussianBlur(gray, (5, 5), 1.2)

    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.1,
        minDist=height * 0.16,
        param1=100,
        param2=26,
        minRadius=int(height * 0.05),
        maxRadius=int(height * 0.15),
    )
    return 0 if circles is None else len(circles[0])


@dataclass(frozen=True)
class GoldClassification:
    tile_id: str
    category: str
    is_gold: bool
    method: str
    evidence_count: int
    second_best_evidence_count: int
    pip_count: int | None = None
    safe_for_executor: bool = False


class GoldTileClassifier:
    """Classify the underlying tile identity of a gold-skinned tile."""

    def __init__(self, descriptors):
        self.descriptors = {
            tile_id: tuple(values)
            for tile_id, values in descriptors.items()
            if values
        }
        if not self.descriptors:
            raise ValueError("No reviewed non-gold templates are available")

    @classmethod
    def from_dataset(cls, dataset_root):
        root = Path(dataset_root)
        descriptors = defaultdict(list)
        for label in approved_labels(root):
            if label["region"] == "gold_region":
                continue
            descriptor = _sift_descriptor(_crop_label(root, label))
            if descriptor is not None:
                descriptors[label["tile_id"]].append(descriptor)
        return cls(descriptors)

    def _rank(self, image):
        sample = _sift_descriptor(image)
        scores = {}
        for tile_id, templates in self.descriptors.items():
            scores[tile_id] = max(
                (_good_sift_matches(sample, template) for template in templates),
                default=0,
            )
        return sorted(
            scores.items(), key=lambda item: (item[1], item[0]), reverse=True
        )

    def classify(self, image):
        ranking = self._rank(image)
        if not ranking:
            raise ValueError("No candidate gold tile classes are available")

        tile_id, best = ranking[0]
        second = ranking[1][1] if len(ranking) > 1 else 0
        method = "sift"
        pip_count = None

        # In the current Huian skin, SIFT reliably identifies the tong family,
        # while the gold overlay can still confuse nearby pip counts. Count pips
        # as a second stage when the best SIFT candidate is a tong tile.
        if tile_id.startswith("P"):
            pip_count = count_tong_pips(image)
            candidate = f"P{pip_count}"
            if 1 <= pip_count <= 9 and candidate in self.descriptors:
                tile_id = candidate
                method = "sift_suit+hough_pips"

        return GoldClassification(
            tile_id=tile_id,
            category=category_for(tile_id),
            is_gold=True,
            method=method,
            evidence_count=best,
            second_best_evidence_count=second,
            pip_count=pip_count,
            safe_for_executor=False,
        )
