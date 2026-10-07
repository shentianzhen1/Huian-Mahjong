"""Development-only A/B for ordinary concealed template preprocessing.

This module must not change Runtime inference.  It compares the current
TemplateTileClassifier feature path against a small central-edge trim while
holding query crops, source-session exclusion and the Runtime threshold fixed.

`source_session` leave-one-out is only a historical regression diagnostic; it
is not evidence of independent original matches.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
from PIL import Image

from workspace.vision.tiles_v0_1.labels import approved_labels
from workspace.vision.tiles_v0_1.template_classifier import (
    _canonical_region,
    _feature,
    _normalize_tile_face,
)

RUNTIME_THRESHOLD = 0.82
CONCEALED_REGIONS = frozenset({"hand_region", "draw_visual"})
CENTRAL_X_TRIM = 0.07
CENTRAL_Y_TRIM = 0.04
FEATURE_SIZE = (48, 72)


@dataclass(frozen=True)
class SampleResult:
    sample_key: str
    truth: str
    predicted: str | None
    confidence: float
    accepted: bool
    correct: bool
    region: str
    source_session: str


@dataclass(frozen=True)
class Aggregate:
    total: int
    scorable: int
    raw_correct: int
    accepted: int
    accepted_correct: int
    wrong_accepted: int
    rejected: int
    raw_accuracy: float
    accepted_accuracy: float | None


def _sample_key(row: dict) -> str:
    return str(
        row.get("id")
        or f"{row.get('image')}|{row.get('source_frame')}|{row.get('bbox')}"
    )


def _concealed_rows(dataset_root: str | Path) -> list[dict]:
    rows = []
    for row in approved_labels(dataset_root):
        region = _canonical_region(row.get("region"))
        if region not in CONCEALED_REGIONS:
            continue
        if row.get("gold_skin_only"):
            continue
        session = row.get("source_session")
        tile_id = row.get("tile_id")
        if not isinstance(session, str) or not session:
            continue
        if not isinstance(tile_id, str) or not tile_id:
            continue
        rows.append(row)
    return rows


def _load_crop(dataset_root: Path, row: dict) -> Image.Image:
    image_path = dataset_root / row["image"]
    with Image.open(image_path) as source:
        image = source.convert("RGB")
        if Path(row["image"]).parts[:1] == ("templates",):
            return image.copy()
        x, y, width, height = (int(value) for value in row["bbox"])
        return image.crop((x, y, x + width, y + height)).copy()


def central7_feature(image: Image.Image) -> np.ndarray:
    """Current ordinary normalization plus a conservative central edge trim."""
    normalized = _normalize_tile_face(image)
    width, height = normalized.size
    left = int(round(width * CENTRAL_X_TRIM))
    right = int(round(width * (1.0 - CENTRAL_X_TRIM)))
    top = int(round(height * CENTRAL_Y_TRIM))
    bottom = int(round(height * (1.0 - CENTRAL_Y_TRIM)))
    if right - left >= 8 and bottom - top >= 12:
        normalized = normalized.crop((left, top, right, bottom))
    rgb = np.asarray(normalized.convert("RGB").resize(FEATURE_SIZE))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    return cv2.equalizeHist(gray)


def baseline_feature(image: Image.Image) -> np.ndarray:
    return _feature(image, region="concealed_identity")


def _precompute_features(
    dataset_root: Path,
    rows: list[dict],
    feature_fn: Callable[[Image.Image], np.ndarray],
) -> dict[str, np.ndarray]:
    """Extract each reviewed crop once; split logic only reuses cached tensors."""
    return {
        _sample_key(row): feature_fn(_load_crop(dataset_root, row))
        for row in rows
    }


def _feature_bank(
    rows: list[dict],
    features: dict[str, np.ndarray],
) -> dict[str, list[np.ndarray]]:
    bank: dict[str, list[np.ndarray]] = defaultdict(list)
    for row in rows:
        bank[row["tile_id"]].append(features[_sample_key(row)])
    return dict(bank)


def _classify_feature(
    sample: np.ndarray,
    bank: dict[str, list[np.ndarray]],
) -> tuple[str | None, float]:
    best_tile: str | None = None
    best_score = float("-inf")
    for tile_id, examples in bank.items():
        score = max(
            float(cv2.matchTemplate(sample, template, cv2.TM_CCOEFF_NORMED)[0, 0])
            for template in examples
        )
        if not np.isfinite(score):
            score = -1.0
        if score > best_score:
            best_tile = tile_id
            best_score = score
    return best_tile, max(0.0, best_score) if best_tile is not None else 0.0


def evaluate_feature(
    dataset_root: str | Path,
    feature_fn: Callable[[Image.Image], np.ndarray],
    *,
    pooled_concealed: bool = True,
) -> list[SampleResult]:
    """Leave one source_session out using identical approved query crops."""
    root = Path(dataset_root)
    rows = _concealed_rows(root)
    features = _precompute_features(root, rows, feature_fn)
    results: list[SampleResult] = []
    for query in rows:
        query_region = _canonical_region(query["region"])
        train = [
            row
            for row in rows
            if row["source_session"] != query["source_session"]
            and (
                pooled_concealed
                or _canonical_region(row["region"]) == query_region
            )
        ]
        bank = _feature_bank(train, features)
        predicted, confidence = _classify_feature(
            features[_sample_key(query)], bank
        )
        accepted = predicted is not None and confidence >= RUNTIME_THRESHOLD
        results.append(
            SampleResult(
                sample_key=_sample_key(query),
                truth=query["tile_id"],
                predicted=predicted,
                confidence=confidence,
                accepted=accepted,
                correct=predicted == query["tile_id"],
                region=query_region,
                source_session=query["source_session"],
            )
        )
    return results


def aggregate(results: list[SampleResult]) -> Aggregate:
    scorable = [row for row in results if row.predicted is not None]
    accepted = [row for row in results if row.accepted]
    raw_correct = sum(row.correct for row in scorable)
    accepted_correct = sum(row.correct for row in accepted)
    wrong_accepted = len(accepted) - accepted_correct
    return Aggregate(
        total=len(results),
        scorable=len(scorable),
        raw_correct=raw_correct,
        accepted=len(accepted),
        accepted_correct=accepted_correct,
        wrong_accepted=wrong_accepted,
        rejected=len(results) - len(accepted),
        raw_accuracy=(raw_correct / len(scorable)) if scorable else 0.0,
        accepted_accuracy=(accepted_correct / len(accepted)) if accepted else None,
    )


def confusion_counts(results: list[SampleResult]) -> dict[str, int]:
    counts = Counter(
        f"{row.truth}->{row.predicted}"
        for row in results
        if row.predicted is not None and not row.correct
    )
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def build_ab_report(dataset_root: str | Path) -> dict[str, object]:
    report: dict[str, object] = {
        "schema_version": "concealed_template_preprocess_ab_v0_1",
        "development_only": True,
        "runtime_changed": False,
        "source_session_is_independent_match_evidence": False,
        "threshold": RUNTIME_THRESHOLD,
        "central7": {
            "x_trim_each_side": CENTRAL_X_TRIM,
            "y_trim_each_side": CENTRAL_Y_TRIM,
        },
        "modes": {},
    }
    for mode_name, pooled in (("pooled_concealed", True), ("same_region", False)):
        baseline = evaluate_feature(dataset_root, baseline_feature, pooled_concealed=pooled)
        candidate = evaluate_feature(dataset_root, central7_feature, pooled_concealed=pooled)
        baseline_keys = [row.sample_key for row in baseline]
        candidate_keys = [row.sample_key for row in candidate]
        if baseline_keys != candidate_keys:
            raise AssertionError("A/B query crops are not identical")
        report["modes"][mode_name] = {
            "baseline": asdict(aggregate(baseline)),
            "central7": asdict(aggregate(candidate)),
            "baseline_confusions": confusion_counts(baseline),
            "central7_confusions": confusion_counts(candidate),
            "same_query_count": len(baseline_keys),
        }
    return report


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="dataset/tiles_runtime_v0_2")
    args = parser.parse_args()
    print(json.dumps(build_ab_report(args.dataset), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
