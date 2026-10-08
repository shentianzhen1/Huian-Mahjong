"""Offline A/B for class-agnostic opened-Gold appearance normalization.

This diagnostic consumes the actual detector classification crops exported by
``whole_hand_baseline_export`` and compares fixed, tile-class-agnostic feature
normalizations against the same reviewed template bank.  It is deliberately
separate from Runtime/Hint: candidate scores are ranking diagnostics, never
calibrated Runtime confidence, and the frozen 0.82 threshold is not changed.

When a reviewed exact-SHA -> original-match registry is supplied, the strict
view excludes every template from the query's original match and excludes
unknown lineage.  ``source_session`` is never used as independence evidence.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from workspace.vision.tiles_runtime_v0_2.opened_gold_identity_probe import (
    FROZEN_THRESHOLD,
    summarize_examples,
    summarize_match_disjoint_examples,
)

NORMALIZATION_MODES = (
    "runtime_gray",
    "face_only_gray",
    "face_only_edges",
    "inner_08_gray",
    "inner_08_edges",
)


def _crop_label_image(source, label):
    """Return the same reviewed tile crop shape used by the Runtime bank."""
    crop = source.convert("RGB")
    if Path(label["image"]).parts[:1] != ("templates",):
        x, y, width, height = label["bbox"]
        crop = crop.crop((x, y, x + width, y + height))
    return crop


def _face_only(image):
    """Keep the dominant bright tile face without production's fixed rim trim."""
    from workspace.vision.tiles_v0_1.template_classifier import _tile_face_box

    image = image.convert("RGB")
    box = _tile_face_box(image, brightness_threshold=100)
    if box is None:
        return image
    x, y, width, height = box
    return image.crop((x, y, x + width, y + height))


def _trim_fraction(image, fraction: float):
    """Apply one symmetric class-agnostic inner trim to a detected tile face."""
    if not 0 <= fraction < 0.25:
        raise ValueError("trim fraction must be in [0, 0.25)")
    image = _face_only(image)
    width, height = image.size
    dx = int(round(width * fraction))
    dy = int(round(height * fraction))
    if width - 2 * dx >= 8 and height - 2 * dy >= 12:
        return image.crop((dx, dy, width - dx, height - dy))
    return image


def _gray_feature(image, *, trim_fraction: float):
    """Build a fixed-size equalized gray feature and suppress the UI Gold badge."""
    import cv2
    import numpy as np

    normalized = _trim_fraction(image, trim_fraction)
    rgb = np.asarray(normalized.convert("RGB").resize((48, 72)))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    # Keep the same relative badge-suppression area as the production feature.
    fill = int(np.median(gray[20:36, 34:48]))
    gray[:20, 34:48] = fill
    return cv2.equalizeHist(gray)


def _edge_feature(gray):
    """Convert one gray feature to illumination-robust gradient magnitude."""
    import cv2
    import numpy as np

    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = cv2.magnitude(gx, gy)
    maximum = float(magnitude.max())
    if not math.isfinite(maximum) or maximum <= 1e-6:
        return np.zeros_like(gray, dtype=np.uint8)
    return np.clip(magnitude * (255.0 / maximum), 0, 255).astype(np.uint8)


def feature_for_mode(image, mode: str):
    """Return one fixed candidate feature without consulting the tile identity."""
    if mode not in NORMALIZATION_MODES:
        raise ValueError(f"unknown opened-Gold normalization mode: {mode}")
    if mode == "runtime_gray":
        from workspace.vision.tiles_v0_1.template_classifier import _feature

        # Exact production feature path; this is the A/B baseline.
        return _feature(image, region="gold_region")
    if mode == "face_only_gray":
        return _gray_feature(image, trim_fraction=0.0)
    if mode == "face_only_edges":
        return _edge_feature(_gray_feature(image, trim_fraction=0.0))
    if mode == "inner_08_gray":
        return _gray_feature(image, trim_fraction=0.08)
    return _edge_feature(_gray_feature(image, trim_fraction=0.08))


def _score_examples(query, bank):
    import cv2
    import numpy as np

    query_degenerate = float(np.std(query)) < 1e-6
    examples = []
    for label, feature in bank:
        degenerate = query_degenerate or float(np.std(feature)) < 1e-6
        score = None if degenerate else float(
            cv2.matchTemplate(query, feature, cv2.TM_CCOEFF_NORMED)[0, 0]
        )
        examples.append({
            "tile_id": label["tile_id"],
            "image": label["image"],
            "source_sha256": label.get("sha256"),
            "source_session": label.get("source_session"),
            "source_region": label.get("region"),
            "gold_skin_only": bool(label.get("gold_skin_only")),
            "feature_degenerate": degenerate,
            "score": score,
        })
    return examples


def summarize_normalization_samples(samples, modes=NORMALIZATION_MODES):
    """Aggregate ranking-only results without applying the Runtime threshold."""
    policies = ("current_bank", "exact_source_filtered", "reviewed_match_disjoint")
    summary = {}
    for policy in policies:
        policy_summary = {}
        for mode in modes:
            rows = []
            for sample in samples:
                if sample.get("status") != "SCORED_DETECTOR_CROP":
                    continue
                result = sample.get("normalizations", {}).get(mode, {}).get(policy)
                if result is not None:
                    rows.append(result)
            expected_scores = [
                row["expected_class_winner"]["score"]
                for row in rows
                if row.get("expected_class_winner") is not None
                and isinstance(row["expected_class_winner"].get("score"), (int, float))
                and not isinstance(row["expected_class_winner"].get("score"), bool)
                and math.isfinite(row["expected_class_winner"]["score"])
            ]
            policy_summary[mode] = {
                "sample_count": len(rows),
                "top1_correct": sum(
                    row.get("candidate_tile") == row.get("expected_tile") for row in rows
                ),
                "expected_class_rank1": sum(row.get("expected_class_rank") == 1 for row in rows),
                "expected_class_score_mean": (
                    sum(expected_scores) / len(expected_scores) if expected_scores else None
                ),
                "runtime_threshold_applied": False,
                "scores_are_runtime_acceptance": False,
                "formal_promotion_evidence": False,
            }
        summary[policy] = policy_summary
    return summary


def probe_normalizations(
    export_path,
    dataset_root,
    *,
    expected_tile,
    modes=NORMALIZATION_MODES,
    lineage_path=None,
    repository_root=None,
):
    """Score fixed normalization candidates on actual exported detector crops."""
    from PIL import Image
    from workspace.vision.tiles_v0_1.labels import approved_labels

    modes = tuple(modes)
    if not modes or len(set(modes)) != len(modes):
        raise ValueError("normalization modes must be a non-empty unique sequence")
    for mode in modes:
        if mode not in NORMALIZATION_MODES:
            raise ValueError(f"unknown opened-Gold normalization mode: {mode}")

    export_path, dataset_root = Path(export_path), Path(dataset_root)
    export = json.loads(export_path.read_text(encoding="utf-8"))
    source_sha = export["source"]["sha256"]

    lineage = None
    if lineage_path is not None:
        from workspace.vision.concealed_template_match_lineage import (
            load_concealed_template_lineage,
            verify_lineage_evidence_paths,
        )
        if repository_root is None:
            raise ValueError("repository_root is required to verify lineage evidence paths")
        lineage = load_concealed_template_lineage(lineage_path)
        issues = verify_lineage_evidence_paths(lineage, repository_root)
        if issues:
            raise ValueError(f"lineage evidence paths failed verification: {issues}")

    labels = approved_labels(dataset_root)
    banks = {mode: [] for mode in modes}
    for label in labels:
        path = dataset_root / label["image"]
        if not path.is_file():
            continue
        with Image.open(path) as source:
            crop = _crop_label_image(source, label)
            for mode in modes:
                banks[mode].append((label, feature_for_mode(crop, mode)))

    samples = []
    for sample in export["samples"]:
        indicators = [
            component for component in sample["components"]
            if component["region_candidate"] == "gold"
        ]
        if len(indicators) != 1:
            samples.append({
                "timestamp_seconds": sample["timestamp_seconds"],
                "status": "EXPLICIT_INDICATOR_COUNT_NOT_ONE",
                "explicit_indicator_count": len(indicators),
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
            crop = source.convert("RGB")
            query_size = list(crop.size)
            normalizations = {}
            for mode in modes:
                examples = _score_examples(feature_for_mode(crop, mode), banks[mode])
                result = {
                    "current_bank": summarize_examples(
                        examples, expected_tile=expected_tile
                    ),
                    "exact_source_filtered": summarize_examples(
                        examples,
                        expected_tile=expected_tile,
                        excluded_source_shas=[source_sha],
                    ),
                }
                if lineage is not None:
                    result["reviewed_match_disjoint"] = summarize_match_disjoint_examples(
                        examples,
                        expected_tile=expected_tile,
                        source_sha=source_sha,
                        query_match_group=export["original_match_group"],
                        lineage=lineage,
                    )
                normalizations[mode] = result

        samples.append({
            "timestamp_seconds": sample["timestamp_seconds"],
            "status": "SCORED_DETECTOR_CROP",
            "pixel_bbox": component["pixel_bbox"],
            "classification_crop_bbox": component["classification_crop_bbox"],
            "query_size": query_size,
            "runtime_observation": {
                key: component.get(key)
                for key in (
                    "candidate_tile_id",
                    "tile_id",
                    "tile_confidence",
                    "identity_reason",
                )
            },
            "normalizations": normalizations,
        })

    return {
        "schema_version": "opened_gold_normalization_ab_v0_1",
        "status": "DEVELOPMENT_APPEARANCE_DIAGNOSTIC_NOT_PROMOTION",
        "source_sha256": source_sha,
        "original_match_group": export["original_match_group"],
        "expected_opened_tile": expected_tile,
        "expected_identity_authority": "caller_direct_visible_indicator_review",
        "normalization_modes": list(modes),
        "baseline_mode": "runtime_gray",
        "runtime_threshold_reference": FROZEN_THRESHOLD,
        "runtime_threshold_changed": False,
        "runtime_changed": False,
        "hint_changed": False,
        "executor_changed": False,
        "scores_are_runtime_acceptance": False,
        "source_session_is_independence_signal": False,
        "reviewed_match_disjoint_filter_requested": lineage is not None,
        "raw_or_derived_pixels_in_report": False,
        "formal_promotion_evidence": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
        "summary": summarize_normalization_samples(samples, modes),
        "samples": samples,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline_export", type=Path)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--expected-tile", required=True,
                        help="Direct visible indicator review; never inferred from a hand tile")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", action="append", choices=NORMALIZATION_MODES,
                        help="Candidate mode; repeat to restrict the fixed A/B set")
    parser.add_argument("--lineage", type=Path,
                        help="Optional reviewed exact-SHA original-match registry")
    parser.add_argument("--repository-root", type=Path,
                        help="Required with --lineage to verify evidence paths")
    args = parser.parse_args()
    if args.lineage is not None and args.repository_root is None:
        parser.error("--repository-root is required with --lineage")
    modes = tuple(args.mode) if args.mode else NORMALIZATION_MODES
    report = probe_normalizations(
        args.baseline_export,
        args.dataset,
        expected_tile=args.expected_tile,
        modes=modes,
        lineage_path=args.lineage,
        repository_root=args.repository_root,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"Opened-Gold normalization A/B: {len(report['samples'])} checkpoints, "
        f"{len(modes)} modes; no Runtime changes"
    )


if __name__ == "__main__":
    main()
