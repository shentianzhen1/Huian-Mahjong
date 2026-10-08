"""Offline role-invariant opened-Gold identity development probe.

This probe deliberately does not change Runtime acceptance. It compares a real
explicit Gold-region detector crop against reviewed template sources from other
original matches only. The candidate is two-stage:

1. full-face color/layout similarity chooses a coarse tile family;
2. a glyph-normalized descriptor ranks identities inside that family when its
   Top-1 margin is sufficiently clear, otherwise the full-face ranking wins.

The glyph-margin switch is a revealed-development hyperparameter, not Runtime
confidence and never a replacement for the frozen 0.82 identity threshold.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

FROZEN_RUNTIME_THRESHOLD = 0.82
DEVELOPMENT_GLYPH_MARGIN = 0.03


def tile_family(tile_id: str) -> str:
    if isinstance(tile_id, str) and len(tile_id) >= 2:
        prefix, suffix = tile_id[0], tile_id[1:]
        if prefix in {"M", "P", "S"} and suffix.isdigit():
            return prefix
    return "H"


def choose_role_invariant_candidate(
    full_scores: dict[str, float],
    glyph_scores: dict[str, float],
    *,
    glyph_margin: float = DEVELOPMENT_GLYPH_MARGIN,
) -> dict:
    """Choose a development-only candidate from precomputed class scores.

    The full-face scores choose one coarse family. Within that family a clear
    glyph margin may override the full-face class winner. Missing/nonfinite
    scores fail closed by being excluded from the ranking.
    """
    if (
        isinstance(glyph_margin, bool)
        or not isinstance(glyph_margin, (int, float))
        or not math.isfinite(glyph_margin)
        or glyph_margin < 0
    ):
        raise ValueError("glyph_margin must be a finite non-negative number")

    common = {
        tile
        for tile in set(full_scores) & set(glyph_scores)
        if isinstance(full_scores[tile], (int, float))
        and not isinstance(full_scores[tile], bool)
        and math.isfinite(full_scores[tile])
        and isinstance(glyph_scores[tile], (int, float))
        and not isinstance(glyph_scores[tile], bool)
        and math.isfinite(glyph_scores[tile])
    }
    if not common:
        return {
            "candidate_tile": None,
            "family": None,
            "decision_feature": None,
            "glyph_margin": None,
            "development_glyph_margin_switch": float(glyph_margin),
            "scores_are_runtime_confidence": False,
            "runtime_threshold_reference": FROZEN_RUNTIME_THRESHOLD,
            "safe_for_runtime": False,
            "safe_for_hint": False,
            "safe_for_executor": False,
        }

    family_scores: dict[str, float] = {}
    for tile in common:
        fam = tile_family(tile)
        family_scores[fam] = max(family_scores.get(fam, float("-inf")), full_scores[tile])
    family = sorted(family_scores, key=lambda fam: (-family_scores[fam], fam))[0]
    candidates = sorted(tile for tile in common if tile_family(tile) == family)

    full_ranked = sorted(candidates, key=lambda tile: (-full_scores[tile], tile))
    glyph_ranked = sorted(candidates, key=lambda tile: (-glyph_scores[tile], tile))
    margin = (
        glyph_scores[glyph_ranked[0]] - glyph_scores[glyph_ranked[1]]
        if len(glyph_ranked) >= 2
        else float("inf")
    )
    use_glyph = margin >= glyph_margin
    winner = glyph_ranked[0] if use_glyph else full_ranked[0]
    return {
        "candidate_tile": winner,
        "family": family,
        "decision_feature": "glyph" if use_glyph else "full_face",
        "glyph_margin": margin,
        "full_face_winner": full_ranked[0],
        "glyph_winner": glyph_ranked[0],
        "development_glyph_margin_switch": float(glyph_margin),
        "family_scores": family_scores,
        "scores_are_runtime_confidence": False,
        "runtime_threshold_reference": FROZEN_RUNTIME_THRESHOLD,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def _face_rgb(image):
    import numpy as np
    from workspace.vision.tiles_v0_1.template_classifier import _tile_face_box

    rgb = np.asarray(image.convert("RGB"))
    box = _tile_face_box(image)
    if box is not None:
        x, y, width, height = box
        rgb = rgb[y:y + height, x:x + width]
    return rgb


def _appearance_maps(image, *, trim: float = 0.04, size=(64, 96)):
    import cv2
    import numpy as np

    rgb = _face_rgb(image)
    height, width = rgb.shape[:2]
    dx, dy = int(round(width * trim)), int(round(height * trim))
    if width - 2 * dx >= 8 and height - 2 * dy >= 12:
        rgb = rgb[dy:height - dy, dx:width - dx]
    out_width, out_height = size
    rgb = cv2.resize(rgb, (out_width, out_height), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    background = float(np.percentile(gray, 85))
    hue, saturation, value = [hsv[:, :, index] for index in range(3)]
    dark = gray < background - 35
    red = (saturation > 60) & ((hue < 15) | (hue > 170)) & (value < 240)
    green = (saturation > 60) & (hue >= 35) & (hue < 90) & (value < 240)
    blue = (saturation > 60) & (hue >= 90) & (hue < 140) & (value < 240)
    maps = np.stack([dark, red, green, blue], axis=0).astype(np.float32)
    maps[:, :int(0.25 * out_height), int(0.72 * out_width):] = 0
    maps[:, :, :2] = 0
    maps[:, :, -2:] = 0
    maps[:, :2, :] = 0
    maps[:, -2:, :] = 0
    return maps


def _glyph_maps(image, *, trim: float = 0.04, size=(64, 96)):
    import cv2
    import numpy as np

    rgb = _face_rgb(image)
    height, width = rgb.shape[:2]
    dx, dy = int(round(width * trim)), int(round(height * trim))
    if width - 2 * dx >= 8 and height - 2 * dy >= 12:
        rgb = rgb[dy:height - dy, dx:width - dx]
    height, width = rgb.shape[:2]
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    background = float(np.percentile(gray, 85))
    hue, saturation, value = [hsv[:, :, index] for index in range(3)]
    channels = [
        gray < background - 35,
        (saturation > 60) & ((hue < 15) | (hue > 170)) & (value < 240),
        (saturation > 60) & (hue >= 35) & (hue < 90) & (value < 240),
        (saturation > 60) & (hue >= 90) & (hue < 140) & (value < 240),
    ]
    for channel in channels:
        channel[:int(0.26 * height), int(0.72 * width):] = False
    union = np.logical_or.reduce(channels).astype(np.uint8) * 255
    union = cv2.morphologyEx(union, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    ys, xs = np.where(union > 0)
    out_width, out_height = size
    if len(xs) < 10:
        return np.zeros((4, out_height, out_width), dtype=np.float32)
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    result = []
    for channel in channels:
        crop = channel[y0:y1, x0:x1].astype(np.uint8) * 255
        scale = min((out_width - 4) / crop.shape[1], (out_height - 4) / crop.shape[0])
        new_width = max(1, int(round(crop.shape[1] * scale)))
        new_height = max(1, int(round(crop.shape[0] * scale)))
        resized = cv2.resize(crop, (new_width, new_height), interpolation=cv2.INTER_AREA)
        canvas = np.zeros((out_height, out_width), dtype=np.float32)
        left = (out_width - new_width) // 2
        top = (out_height - new_height) // 2
        canvas[top:top + new_height, left:left + new_width] = resized.astype(np.float32) / 255.0
        result.append(canvas)
    return np.stack(result, axis=0)


def _full_face_score(query, template, *, max_shift: int = 4) -> float:
    import cv2
    import numpy as np

    weights = np.asarray((0.6, 1.0, 1.0, 1.0), dtype=np.float32)[:, None, None]
    query = (query * weights).transpose(1, 2, 0).astype(np.float32)
    template = (template * weights).transpose(1, 2, 0).astype(np.float32)
    padded = cv2.copyMakeBorder(
        query, max_shift, max_shift, max_shift, max_shift,
        cv2.BORDER_CONSTANT, value=0,
    )
    scores = cv2.matchTemplate(padded, template, cv2.TM_CCORR_NORMED)
    return -1.0 if np.isnan(scores).all() else float(np.nanmax(scores))


def _glyph_score(query, template) -> float:
    import numpy as np

    query = query.reshape(-1).astype(np.float32)
    template = template.reshape(-1).astype(np.float32)
    denominator = float(np.linalg.norm(query) * np.linalg.norm(template))
    if denominator <= 1e-9:
        return -1.0
    return float(np.dot(query, template) / denominator)


def _load_label_crop(dataset_root: Path, label: dict):
    from PIL import Image

    path = dataset_root / label["image"]
    with Image.open(path) as source:
        image = source.convert("RGB")
        if Path(label["image"]).parts[:1] != ("templates",):
            x, y, width, height = label["bbox"]
            image = image.crop((x, y, x + width, y + height))
        return image.copy()


def score_query(query_image, *, dataset_root: Path, labels: list[dict], lineage,
                query_match_group: str, glyph_margin: float) -> dict:
    from workspace.vision.concealed_template_match_lineage import (
        qualify_concealed_template_labels,
    )

    qualified, audit = qualify_concealed_template_labels(
        labels, lineage, query_match_group=query_match_group
    )
    query_full = _appearance_maps(query_image)
    query_glyph = _glyph_maps(query_image)
    full_scores: dict[str, float] = {}
    glyph_scores: dict[str, float] = {}
    for label in qualified:
        path = dataset_root / label["image"]
        if not path.is_file():
            continue
        template = _load_label_crop(dataset_root, label)
        full = _full_face_score(query_full, _appearance_maps(template))
        glyph = _glyph_score(query_glyph, _glyph_maps(template))
        tile = label["tile_id"]
        full_scores[tile] = max(full_scores.get(tile, float("-inf")), full)
        glyph_scores[tile] = max(glyph_scores.get(tile, float("-inf")), glyph)
    result = choose_role_invariant_candidate(
        full_scores, glyph_scores, glyph_margin=glyph_margin
    )
    result["lineage_audit"] = audit
    result["qualified_class_count"] = len(set(full_scores) & set(glyph_scores))
    result["original_match_disjointness_established"] = bool(
        audit.get("lineage_qualified_label_count")
    )
    return result


def probe_export(export_path: Path, dataset_root: Path, *, expected_tile: str,
                 lineage_path: Path, repository_root: Path,
                 glyph_margin: float = DEVELOPMENT_GLYPH_MARGIN) -> dict:
    from PIL import Image
    from workspace.vision.concealed_template_match_lineage import (
        load_concealed_template_lineage, verify_lineage_evidence_paths,
    )
    from workspace.vision.tiles_v0_1.labels import approved_labels

    export = json.loads(export_path.read_text(encoding="utf-8"))
    lineage = load_concealed_template_lineage(lineage_path)
    issues = verify_lineage_evidence_paths(lineage, repository_root)
    if issues:
        raise ValueError(f"lineage evidence paths failed verification: {issues}")
    labels = approved_labels(dataset_root)
    samples = []
    for sample in export["samples"]:
        indicators = [
            component for component in sample["components"]
            if component.get("region_candidate") == "gold"
        ]
        if len(indicators) != 1:
            samples.append({
                "timestamp_seconds": sample["timestamp_seconds"],
                "status": "EXPLICIT_INDICATOR_COUNT_NOT_ONE",
            })
            continue
        component = indicators[0]
        reference = component.get("private_crop_ref")
        if not reference:
            raise ValueError("export must contain the actual detector classification crop")
        crop_root = (export_path.parent / "crops" / sample["sample_id"]).resolve()
        crop_path = (crop_root / reference).resolve()
        crop_path.relative_to(crop_root)
        with Image.open(crop_path) as source:
            query = source.convert("RGB")
            result = score_query(
                query,
                dataset_root=dataset_root,
                labels=labels,
                lineage=lineage,
                query_match_group=export["original_match_group"],
                glyph_margin=glyph_margin,
            )
        result.update({
            "timestamp_seconds": sample["timestamp_seconds"],
            "status": "SCORED_DETECTOR_CROP",
            "expected_tile": expected_tile,
            "correct": result["candidate_tile"] == expected_tile,
            "current_runtime_candidate": component.get("candidate_tile_id"),
            "current_runtime_confidence": component.get("tile_confidence"),
            "current_runtime_identity_reason": component.get("identity_reason"),
        })
        samples.append(result)
    return {
        "schema_version": "opened_gold_role_invariant_probe_v0_1",
        "status": "REVEALED_DEVELOPMENT_DIAGNOSTIC_NOT_PROMOTION",
        "source_sha256": export["source"]["sha256"],
        "original_match_group": export["original_match_group"],
        "expected_opened_tile": expected_tile,
        "development_glyph_margin_switch": float(glyph_margin),
        "glyph_margin_selected_on_revealed_development_data": True,
        "source_session_is_independence_signal": False,
        "scores_are_runtime_confidence": False,
        "runtime_threshold_reference": FROZEN_RUNTIME_THRESHOLD,
        "runtime_changed": False,
        "hint_changed": False,
        "executor_changed": False,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
        "samples": samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline_export", type=Path)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--expected-tile", required=True)
    parser.add_argument("--lineage", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--glyph-margin", type=float, default=DEVELOPMENT_GLYPH_MARGIN)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = probe_export(
        args.baseline_export,
        args.dataset,
        expected_tile=args.expected_tile,
        lineage_path=args.lineage,
        repository_root=args.repository_root,
        glyph_margin=args.glyph_margin,
    )
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Opened-Gold role-invariant probe: {len(report['samples'])} samples; no Runtime changes")


if __name__ == "__main__":
    main()
