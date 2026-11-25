"""Offline opened-Gold query-size projection A/B probe.

This tool implements a narrow development experiment: reuse reviewed concealed
hand/draw tile crops as 34-class identity references, project each reference to
the *actual opened-indicator face size* seen in the query crop, then compare
that synthetic Gold-domain bank with the existing baseline. Projection variants
model resize/anti-aliasing differences only. They do not create new source
lineage, do not count as independent matches, and are never Runtime confidence.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from workspace.vision.tiles_runtime_v0_2.opened_gold_identity_probe import (
    probe_export as probe_baseline_export,
    summarize_examples,
    summarize_match_disjoint_examples,
)


_PROJECTION_VARIANTS = (
    ("query_size_bicubic", "BICUBIC", 0.0),
    ("query_size_lanczos", "LANCZOS", 0.0),
    ("query_size_bicubic_blur_045", "BICUBIC", 0.45),
)


def _projected_gold_features(image, target_face_size):
    """Return class-agnostic query-size Gold-domain feature variants.

    The input remains the reviewed ordinary tile crop. We first isolate its
    bright tile face, resize that face to the real opened-indicator face size,
    optionally add a tiny blur to mimic UI anti-aliasing, then run the unchanged
    Gold feature path. No tile-specific transform is allowed.
    """
    from PIL import Image, ImageFilter
    from workspace.vision.tiles_v0_1.template_classifier import (
        _feature,
        _normalize_tile_face,
    )

    width, height = (int(target_face_size[0]), int(target_face_size[1]))
    if width < 8 or height < 12:
        raise ValueError("target opened-indicator face is too small")

    face = _normalize_tile_face(image).convert("RGB")
    resampling = getattr(Image, "Resampling", Image)
    features = {}
    for name, resample_name, blur_radius in _PROJECTION_VARIANTS:
        resample = getattr(resampling, resample_name)
        rendered = face.resize((width, height), resample=resample)
        if blur_radius:
            rendered = rendered.filter(ImageFilter.GaussianBlur(blur_radius))
        features[name] = _feature(rendered, region="gold_region")
    return features


def _load_label_crops(dataset_root):
    from PIL import Image
    from workspace.vision.tiles_v0_1.labels import approved_labels

    root = Path(dataset_root)
    rows = []
    for label in approved_labels(root):
        path = root / label["image"]
        if not path.is_file():
            continue
        with Image.open(path) as source:
            source = source.convert("RGB")
            if Path(label["image"]).parts[:1] == ("templates",):
                crop = source.copy()
            else:
                x, y, width, height = label["bbox"]
                if x + width > source.width or y + height > source.height:
                    continue
                crop = source.crop((x, y, x + width, y + height))
        rows.append((dict(label), crop))
    return rows


def _score_projected_bank(query_crop, label_crops, target_face_size):
    import cv2
    import numpy as np
    from workspace.vision.tiles_v0_1.template_classifier import _feature

    query = _feature(query_crop, region="gold_region")
    query_degenerate = float(np.std(query)) < 1e-6
    rows = []
    for label, crop in label_crops:
        variants = _projected_gold_features(crop, target_face_size)
        for variant_name, feature in variants.items():
            degenerate = query_degenerate or float(np.std(feature)) < 1e-6
            score = None if degenerate else float(
                cv2.matchTemplate(query, feature, cv2.TM_CCOEFF_NORMED)[0, 0]
            )
            rows.append({
                "tile_id": label["tile_id"],
                "image": label["image"],
                "source_sha256": label.get("sha256"),
                "source_session": label.get("source_session"),
                "source_region": label.get("region"),
                "gold_skin_only": bool(label.get("gold_skin_only")),
                "projection_variant": variant_name,
                "projection_target_face_size": list(target_face_size),
                "feature_degenerate": degenerate,
                "score": score,
            })
    return rows


def _compact_delta(baseline, candidate):
    baseline_score = baseline.get("candidate_score")
    candidate_score = candidate.get("candidate_score")
    return {
        "baseline_candidate": baseline.get("candidate_tile"),
        "candidate_candidate": candidate.get("candidate_tile"),
        "baseline_expected_class_rank": baseline.get("expected_class_rank"),
        "candidate_expected_class_rank": candidate.get("expected_class_rank"),
        "baseline_candidate_score": baseline_score,
        "candidate_candidate_score": candidate_score,
        "candidate_score_delta": (
            candidate_score - baseline_score
            if isinstance(candidate_score, (int, float))
            and isinstance(baseline_score, (int, float))
            and math.isfinite(candidate_score)
            and math.isfinite(baseline_score)
            else None
        ),
    }


def probe_scale_projection(
    export_path,
    dataset_root,
    *,
    expected_tile,
    lineage_path=None,
    repository_root=None,
):
    """Compare baseline vs query-size-projected references on the same crops."""
    from PIL import Image
    from workspace.vision.concealed_template_match_lineage import (
        load_concealed_template_lineage,
        verify_lineage_evidence_paths,
    )
    from workspace.vision.tiles_v0_1.template_classifier import _tile_face_box

    export_path = Path(export_path)
    dataset_root = Path(dataset_root)
    export = json.loads(export_path.read_text(encoding="utf-8"))
    baseline = probe_baseline_export(
        export_path,
        dataset_root,
        expected_tile=expected_tile,
        lineage_path=lineage_path,
        repository_root=repository_root,
    )

    lineage = None
    if lineage_path is not None:
        if repository_root is None:
            raise ValueError("repository_root is required with lineage_path")
        lineage = load_concealed_template_lineage(lineage_path)
        issues = verify_lineage_evidence_paths(lineage, repository_root)
        if issues:
            raise ValueError(f"lineage evidence paths failed verification: {issues}")

    label_crops = _load_label_crops(dataset_root)
    baseline_by_time = {
        row["timestamp_seconds"]: row for row in baseline["samples"]
    }
    samples = []
    source_sha = export["source"]["sha256"]
    query_group = export["original_match_group"]

    for sample in export["samples"]:
        timestamp = sample["timestamp_seconds"]
        base = baseline_by_time.get(timestamp, {})
        indicators = [
            component for component in sample["components"]
            if component.get("region_candidate") == "gold"
        ]
        if len(indicators) != 1:
            samples.append({
                "timestamp_seconds": timestamp,
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
            query_crop = source.convert("RGB")
            box = _tile_face_box(query_crop)
        if box is None:
            samples.append({
                "timestamp_seconds": timestamp,
                "status": "QUERY_BRIGHT_FACE_NOT_FOUND",
            })
            continue
        _, _, face_width, face_height = box
        rows = _score_projected_bank(
            query_crop,
            label_crops,
            (face_width, face_height),
        )
        projected_full = summarize_examples(rows, expected_tile=expected_tile)
        projected_filtered = summarize_examples(
            rows,
            expected_tile=expected_tile,
            excluded_source_shas=[source_sha],
        )
        result = {
            "timestamp_seconds": timestamp,
            "status": "SCORED_QUERY_SIZE_PROJECTED_REFERENCE_BANK",
            "query_face_size": [face_width, face_height],
            "projection_variants": [name for name, _, _ in _PROJECTION_VARIANTS],
            "baseline_current_bank": base.get("current_bank"),
            "projected_current_bank": projected_full,
            "baseline_exact_source_filtered": base.get("exact_source_filtered"),
            "projected_exact_source_filtered": projected_filtered,
            "full_bank_delta": _compact_delta(
                base.get("current_bank", {}), projected_full
            ),
            "exact_source_filtered_delta": _compact_delta(
                base.get("exact_source_filtered", {}), projected_filtered
            ),
        }
        if lineage is not None:
            projected_disjoint = summarize_match_disjoint_examples(
                rows,
                expected_tile=expected_tile,
                source_sha=source_sha,
                query_match_group=query_group,
                lineage=lineage,
            )
            result["baseline_reviewed_match_disjoint"] = base.get(
                "reviewed_match_disjoint"
            )
            result["projected_reviewed_match_disjoint"] = projected_disjoint
            result["reviewed_match_disjoint_delta"] = _compact_delta(
                base.get("reviewed_match_disjoint", {}), projected_disjoint
            )
        samples.append(result)

    return {
        "schema_version": "opened_gold_scale_projection_probe_v0_1",
        "status": "DEVELOPMENT_SYNTHETIC_DOMAIN_AB_NOT_RUNTIME_POLICY",
        "source_sha256": source_sha,
        "original_match_group": query_group,
        "expected_opened_tile": expected_tile,
        "projection_scope": "class_agnostic_query_face_size_resize_and_antialias",
        "synthetic_variants_create_new_independent_sources": False,
        "source_session_is_independence_signal": False,
        "runtime_threshold_changed": False,
        "runtime_changed": False,
        "hint_changed": False,
        "executor_changed": False,
        "scores_are_runtime_acceptance": False,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
        "samples": samples,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline_export", type=Path)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--expected-tile", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lineage", type=Path)
    parser.add_argument("--repository-root", type=Path)
    args = parser.parse_args()
    if args.lineage is not None and args.repository_root is None:
        parser.error("--repository-root is required with --lineage")
    report = probe_scale_projection(
        args.baseline_export,
        args.dataset,
        expected_tile=args.expected_tile,
        lineage_path=args.lineage,
        repository_root=args.repository_root,
    )
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"Opened-Gold scale projection A/B: {len(report['samples'])} checkpoints; "
        "no Runtime changes"
    )


if __name__ == "__main__":
    main()
