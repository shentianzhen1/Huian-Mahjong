"""Development-only SIFT matcher for exposed-meld tile identity.

The existing public identity shadow uses whole-face grayscale correlation.
Private retrospective evidence suggests that local keypoints are more tolerant
of the scale/rendering differences seen in exposed melds. This module explores
that hypothesis without changing Runtime, Hint, Executor, or existing gates.

Only reviewed public_meld templates are used. Query match group and exact source
SHA are excluded before ranking, and a class is eligible only when it is
supported by the requested number of *other original match groups*.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from workspace.vision.public_identity_labels import (
    PublicIdentityManifest,
    approved_labels,
    pixel_bbox,
    verify_repository_files,
)
from workspace.vision.public_identity_shadow_v0_2 import (
    SourceGroup,
    load_development_sources,
)


SIFT_SCALE_FACTOR = 3.0
SIFT_CLAHE_CLIP_LIMIT = 2.0
SIFT_CLAHE_TILE_GRID = (8, 8)
SIFT_NFEATURES = 100
SIFT_KNN_K = 2
SIFT_RATIO_TEST = 0.80
SIFT_FALLBACK_RAW_MATCHES = 5
SIFT_MINIMUM_OTHER_MATCH_GROUPS = 2


@dataclass(frozen=True)
class PublicMeldSiftTemplate:
    tile_id: str
    source_session: str
    source_sha256: str
    match_group: str
    descriptors: Any


@dataclass(frozen=True)
class PublicMeldSiftBank:
    sources: dict[str, SourceGroup]
    templates: tuple[PublicMeldSiftTemplate, ...]


def _sift_descriptors(image: Any) -> Any | None:
    """Extract local descriptors from one already-cropped public meld face."""
    import cv2
    import numpy as np

    rgb = np.asarray(image.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    gray = cv2.resize(
        gray,
        None,
        fx=SIFT_SCALE_FACTOR,
        fy=SIFT_SCALE_FACTOR,
        interpolation=cv2.INTER_CUBIC,
    )
    gray = cv2.createCLAHE(
        clipLimit=SIFT_CLAHE_CLIP_LIMIT,
        tileGridSize=SIFT_CLAHE_TILE_GRID,
    ).apply(gray)
    detector = cv2.SIFT_create(nfeatures=SIFT_NFEATURES)
    _keypoints, descriptors = detector.detectAndCompute(gray, None)
    if descriptors is None or len(descriptors) < 2:
        return None
    return descriptors.astype("float32", copy=False)


def _descriptor_similarity(first: Any, second: Any) -> float | None:
    """Return a development-only similarity where larger is better.

    KNN ratio-filtered matches are preferred. When none survive, the mean of a
    few best raw matches is retained so sparse faces abstain by ranking rather
    than throwing. This score has no Runtime probability interpretation.
    """
    import cv2
    import numpy as np

    if first is None or second is None or len(first) < 2 or len(second) < 2:
        return None
    matcher = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
    pairs = matcher.knnMatch(first, second, k=SIFT_KNN_K)
    good_distances: list[float] = []
    for pair in pairs:
        if len(pair) != SIFT_KNN_K:
            continue
        best, runner = pair
        if best.distance < SIFT_RATIO_TEST * runner.distance:
            good_distances.append(float(best.distance))

    if not good_distances:
        raw = matcher.match(first, second)
        if not raw:
            return None
        best_raw = sorted(float(match.distance) for match in raw)[
            :SIFT_FALLBACK_RAW_MATCHES
        ]
        good_distances = best_raw

    mean_distance = float(np.mean(good_distances))
    return float(len(good_distances) / (1.0 + mean_distance))


def build_public_meld_sift_bank(
    manifest: PublicIdentityManifest,
    repository_root: str | Path,
    registry_path: str | Path,
) -> PublicMeldSiftBank:
    """Build a verified development bank from approved public_meld crops."""
    from PIL import Image

    root = Path(repository_root).resolve()
    sources = load_development_sources(registry_path)
    integrity = verify_repository_files(manifest, root)
    if integrity:
        raise ValueError(
            "public identity source integrity failed: " + ",".join(integrity)
        )

    templates: list[PublicMeldSiftTemplate] = []
    for label in approved_labels(manifest):
        if label.region != "public_meld":
            continue
        source = sources.get(label.source_session)
        if source is None or source.source_sha256 != label.source_sha256:
            raise ValueError("public meld label source registry mismatch")
        image_path = (root / label.image_path).resolve()
        if root not in image_path.parents:
            raise ValueError("public meld template path escapes repository root")
        with Image.open(image_path) as original:
            image = original.convert("RGB")
            x, y, width, height = pixel_bbox(label, image.size)
            crop = image.crop((x, y, x + width, y + height))
        descriptors = _sift_descriptors(crop)
        if descriptors is None:
            continue
        templates.append(
            PublicMeldSiftTemplate(
                tile_id=label.tile_id,
                source_session=label.source_session,
                source_sha256=label.source_sha256,
                match_group=source.match_group,
                descriptors=descriptors,
            )
        )
    return PublicMeldSiftBank(sources=sources, templates=tuple(templates))


def rank_public_meld_sift(
    bank: PublicMeldSiftBank,
    image: Any,
    *,
    source_session: str,
    source_sha256: str,
    minimum_other_match_groups: int = SIFT_MINIMUM_OTHER_MATCH_GROUPS,
) -> dict[str, Any]:
    """Rank source-disjoint classes using independent original-match support."""
    if (
        isinstance(minimum_other_match_groups, bool)
        or not isinstance(minimum_other_match_groups, int)
        or minimum_other_match_groups < 1
    ):
        raise ValueError("minimum_other_match_groups must be >= 1")

    source = bank.sources.get(source_session)
    if source is None or source.source_sha256 != source_sha256:
        raise ValueError("query source session/SHA not in locked registry")

    query = _sift_descriptors(image)
    result: dict[str, Any] = {
        "schema_version": "public_meld_sift_rank_v0_1",
        "top1_tile": None,
        "top1_score": None,
        "runner_up_tile": None,
        "runner_up_score": None,
        "margin": None,
        "eligible_class_count": 0,
        "minimum_other_match_groups": minimum_other_match_groups,
        "development_only": True,
        "source_disjoint_ranking": True,
        "changes_runtime_behavior": False,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
        "reason": "insufficient_cross_match_class_support",
    }
    if query is None:
        result["reason"] = "insufficient_sift_keypoints"
        return result

    best_by_class_and_group: dict[str, dict[str, float]] = defaultdict(dict)
    for template in bank.templates:
        if (
            template.match_group == source.match_group
            or template.source_sha256 == source_sha256
        ):
            continue
        score = _descriptor_similarity(query, template.descriptors)
        if score is None:
            continue
        old = best_by_class_and_group[template.tile_id].get(
            template.match_group, float("-inf")
        )
        best_by_class_and_group[template.tile_id][template.match_group] = max(
            old, score
        )

    eligible: list[tuple[str, float, int]] = []
    for tile_id, by_group in best_by_class_and_group.items():
        group_scores = sorted(by_group.values(), reverse=True)
        if len(group_scores) < minimum_other_match_groups:
            continue
        conservative_score = group_scores[minimum_other_match_groups - 1]
        eligible.append((tile_id, conservative_score, len(group_scores)))

    eligible.sort(key=lambda row: (-row[1], row[0]))
    result["eligible_class_count"] = len(eligible)
    if not eligible:
        return result

    winner, score, group_count = eligible[0]
    result["top1_tile"] = winner
    result["top1_score"] = round(float(score), 8)
    result["winner_other_match_groups"] = group_count
    if len(eligible) > 1:
        runner, runner_score, _ = eligible[1]
        result["runner_up_tile"] = runner
        result["runner_up_score"] = round(float(runner_score), 8)
        result["margin"] = round(float(score - runner_score), 8)
    result["reason"] = "development_source_disjoint_ranking"
    return result
