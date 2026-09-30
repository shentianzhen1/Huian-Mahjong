"""Development-only A/B for public_meld identity features.

This experiment answers one narrow question: can a feature designed for exposed
meld faces improve source-disjoint ranking on the two currently eligible
first-hand query classes (P6 and S4) without changing Runtime policy?

It deliberately keeps the existing evidence model:
- query match_group is excluded;
- a candidate class needs support from >=2 other independent match groups;
- same-match clips/hands count once;
- no score threshold is promoted from this experiment;
- Runtime/Hint/Executor remain unchanged.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from PIL import Image

from workspace.vision.public_identity_labels import (
    approved_labels,
    load_public_identity_manifest,
    pixel_bbox,
    verify_repository_files,
)
from workspace.vision.public_identity_shadow_v0_2 import (
    _feature as legacy_public_feature,
    load_development_sources,
)


FEATURES = ("legacy_gray", "gray_edge", "lab_chroma_edge")


def _l2(values: Any) -> Any | None:
    import numpy as np

    vector = np.asarray(values, dtype=np.float32).reshape(-1)
    if vector.size == 0 or not np.isfinite(vector).all():
        return None
    vector = vector - float(vector.mean())
    length = float(np.linalg.norm(vector))
    if length < 1e-6:
        return None
    return vector / length


def _tight_public_face(image: Any) -> Any:
    """Crop the dominant bright tile face while retaining colored glyph pixels."""
    import cv2
    import numpy as np

    rgb = np.asarray(image.convert("RGB"))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    mask = ((hsv[:, :, 1] < 175) & (hsv[:, :, 2] > 95)).astype(np.uint8) * 255
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        np.ones((5, 5), dtype=np.uint8),
        iterations=1,
    )
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    if count <= 1:
        return image.convert("RGB")

    candidates = []
    frame_area = rgb.shape[0] * rgb.shape[1]
    for index in range(1, count):
        x, y, width, height, area = (int(v) for v in stats[index])
        if (
            area >= 0.18 * frame_area
            and width >= 8
            and height >= 12
            and height >= width
        ):
            candidates.append((area, x, y, width, height))
    if not candidates:
        return image.convert("RGB")

    _, x, y, width, height = max(candidates)
    return image.convert("RGB").crop((x, y, x + width, y + height))


def _channel_feature(channel: Any, *, size: tuple[int, int] = (20, 30)) -> Any | None:
    import cv2

    reduced = cv2.resize(channel, size, interpolation=cv2.INTER_AREA)
    return _l2(reduced)


def _gray_edge_feature(image: Any) -> Any | None:
    import cv2
    import numpy as np

    face = _tight_public_face(image).resize((48, 72), Image.Resampling.BILINEAR)
    rgb = np.asarray(face, dtype=np.uint8)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    gray = cv2.equalizeHist(gray)
    sobel_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    edge = cv2.magnitude(sobel_x, sobel_y)

    gray_part = _channel_feature(gray)
    edge_part = _channel_feature(edge)
    if gray_part is None or edge_part is None:
        return None
    return _l2(np.concatenate((0.55 * gray_part, 0.95 * edge_part)))


def _lab_chroma_edge_feature(image: Any) -> Any | None:
    """Spatial luminance/edge + Lab chroma; intended for colored Mahjong glyphs."""
    import cv2
    import numpy as np

    face = _tight_public_face(image).resize((48, 72), Image.Resampling.BILINEAR)
    rgb = np.asarray(face, dtype=np.uint8)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    luminance = cv2.equalizeHist(lab[:, :, 0].astype(np.uint8)).astype(np.float32)
    a = lab[:, :, 1] - 128.0
    b = lab[:, :, 2] - 128.0
    sobel_x = cv2.Sobel(luminance, cv2.CV_32F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(luminance, cv2.CV_32F, 0, 1, ksize=3)
    edge = cv2.magnitude(sobel_x, sobel_y)

    pieces = [
        _channel_feature(luminance),
        _channel_feature(edge),
        _channel_feature(a),
        _channel_feature(b),
    ]
    if any(piece is None for piece in pieces):
        return None
    return _l2(
        np.concatenate(
            (
                0.35 * pieces[0],
                0.90 * pieces[1],
                0.70 * pieces[2],
                0.70 * pieces[3],
            )
        )
    )


def extract_public_meld_feature(image: Any, feature_name: str) -> Any | None:
    if feature_name == "legacy_gray":
        return legacy_public_feature(image)
    if feature_name == "gray_edge":
        return _gray_edge_feature(image)
    if feature_name == "lab_chroma_edge":
        return _lab_chroma_edge_feature(image)
    raise ValueError(f"unknown public meld feature: {feature_name}")


def _score_query(
    query_feature: Any,
    *,
    expected_tile: str,
    query_match_group: str,
    templates: list[dict[str, Any]],
) -> dict[str, Any]:
    import numpy as np

    best_by_class_and_group: dict[str, dict[str, float]] = defaultdict(dict)
    for row in templates:
        if row["match_group"] == query_match_group:
            continue
        score = float(np.dot(query_feature, row["feature"]))
        old = best_by_class_and_group[row["tile_id"]].get(row["match_group"], -2.0)
        best_by_class_and_group[row["tile_id"]][row["match_group"]] = max(old, score)

    eligible = sorted(
        (
            (tile_id, sorted(group_scores.values(), reverse=True)[1])
            for tile_id, group_scores in best_by_class_and_group.items()
            if len(group_scores) >= 2
        ),
        key=lambda row: (-row[1], row[0]),
    )
    if not eligible:
        return {
            "expected_tile": expected_tile,
            "winner": None,
            "winner_score": None,
            "runner_up": None,
            "runner_up_score": None,
            "margin": None,
            "eligible_class_count": 0,
            "top1_correct": False,
        }

    winner, winner_score = eligible[0]
    runner_up, runner_score = (eligible[1] if len(eligible) > 1 else (None, None))
    margin = (
        winner_score - runner_score
        if runner_score is not None
        else None
    )
    return {
        "expected_tile": expected_tile,
        "winner": winner,
        "winner_score": round(float(winner_score), 6),
        "runner_up": runner_up,
        "runner_up_score": (
            round(float(runner_score), 6) if runner_score is not None else None
        ),
        "margin": round(float(margin), 6) if margin is not None else None,
        "eligible_class_count": len(eligible),
        "top1_correct": winner == expected_tile,
    }


def evaluate_public_meld_features(
    repository_root: str | Path = ".",
    manifest_path: str | Path = (
        "references/vision/2026-09-22/public_identity_labels_v0_1.json"
    ),
    registry_path: str | Path = (
        "references/vision/2026-09-24/"
        "public_identity_source_groups.development.json"
    ),
    query_fixture_path: str | Path = (
        "references/vision/2026-09-30/first_hand_public_query_features_v0_1.json"
    ),
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    manifest = load_public_identity_manifest(root / manifest_path)
    sources = load_development_sources(root / registry_path)
    integrity = verify_repository_files(manifest, root)
    if integrity:
        raise ValueError("public identity source integrity failed: " + ",".join(integrity))

    fixture = json.loads((root / query_fixture_path).read_text(encoding="utf-8"))
    query_source = sources.get(fixture.get("source_session"))
    if query_source is None:
        raise ValueError("query source session is not registered")
    if query_source.source_sha256 != fixture.get("source_sha256"):
        raise ValueError("query source SHA mismatch")
    if query_source.match_group != fixture.get("match_group"):
        raise ValueError("query match group mismatch")

    labels = [
        label for label in approved_labels(manifest)
        if label.region == "public_meld"
    ]
    templates_by_feature: dict[str, list[dict[str, Any]]] = {
        name: [] for name in FEATURES
    }
    for label in labels:
        source = sources.get(label.source_session)
        if source is None or source.source_sha256 != label.source_sha256:
            raise ValueError(f"label source registry mismatch: {label.label_id}")
        image_path = (root / label.image_path).resolve()
        if root not in image_path.parents:
            raise ValueError("public meld label path escapes repository root")
        with Image.open(image_path) as original:
            image = original.convert("RGB")
            x, y, width, height = pixel_bbox(label, image.size)
            crop = image.crop((x, y, x + width, y + height))
        for feature_name in FEATURES:
            feature = extract_public_meld_feature(crop, feature_name)
            if feature is None:
                continue
            templates_by_feature[feature_name].append(
                {
                    "tile_id": label.tile_id,
                    "match_group": source.match_group,
                    "feature": feature,
                }
            )

    reports: dict[str, Any] = {}
    for feature_name in FEATURES:
        query_rows = []
        for query in fixture.get("queries", ()):
            if query.get("region") != "public_meld":
                continue
            image_path = (root / query["image_path"]).resolve()
            if root not in image_path.parents:
                raise ValueError("query image path escapes repository root")
            raw = image_path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != query["image_sha256"]:
                raise ValueError(f"query image SHA mismatch: {query['query_id']}")
            with Image.open(image_path) as original:
                image = original.convert("RGB")
            feature = extract_public_meld_feature(image, feature_name)
            if feature is None:
                query_rows.append(
                    {
                        "query_id": query["query_id"],
                        "expected_tile": query["expected_tile"],
                        "winner": None,
                        "top1_correct": False,
                        "reason": "feature_extraction_failed",
                    }
                )
                continue
            scored = _score_query(
                feature,
                expected_tile=query["expected_tile"],
                query_match_group=query_source.match_group,
                templates=templates_by_feature[feature_name],
            )
            scored["query_id"] = query["query_id"]
            query_rows.append(scored)

        correct = sum(bool(row.get("top1_correct")) for row in query_rows)
        margins = [
            float(row["margin"])
            for row in query_rows
            if row.get("top1_correct") and row.get("margin") is not None
        ]
        reports[feature_name] = {
            "query_count": len(query_rows),
            "top1_correct_count": correct,
            "top1_accuracy": (
                round(correct / len(query_rows), 6) if query_rows else None
            ),
            "minimum_correct_margin": (
                round(min(margins), 6) if margins else None
            ),
            "queries": query_rows,
        }

    return {
        "schema_version": "public_meld_feature_experiment_v0_1",
        "feature_variants": list(FEATURES),
        "template_public_meld_label_count": len(labels),
        "query_fixture": Path(query_fixture_path).name,
        "query_match_group_excluded": True,
        "minimum_other_match_groups_per_class": 2,
        "results": reports,
        "interpretation_policy": (
            "Diagnostic ranking only. Do not transfer numeric thresholds across "
            "feature families; do not change Runtime until more independent "
            "match support exists and a separately reviewed gate is frozen."
        ),
        "changes_runtime_behavior": False,
        "formal_promotion_evidence": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--output")
    args = parser.parse_args()
    report = evaluate_public_meld_features(args.repository_root)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
