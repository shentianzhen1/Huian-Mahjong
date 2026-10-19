"""Fixed development A/B: same existing geometry transform on both face roles."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile


def normalize_single_face(image):
    """Reuse geometry pixels only; group stack/action output is not applicable.

    This is an offline adapter on manually split faces, NOT a replacement for
    group normalization followed by splitting. No identity inset is applied.
    """
    from workspace.vision.public_meld_geometry_normalization import normalize_public_meld_crop
    from workspace.vision.public_tile_detector import PublicGeometryCandidate

    width, height = image.size
    candidate = PublicGeometryCandidate((0, 0, width, height), (0., 0., 1., 1.),
        "bottom_group", 0., 0., None, None)
    result = normalize_public_meld_crop(image, candidate)
    return result.image, {"input_size": [width, height],
        "output_size": list(result.image.size) if result.image is not None else None,
        "rotation_degrees": result.analysis.rotation_degrees,
        "tight_bbox": result.analysis.tight_bbox_in_group,
        "failed": result.image is None,
        "group_stack_classification_used": False}


def compare_controls(modes):
    baseline = {r["label_id"]: r for r in modes["direct_rectangle"]["public_control_rows"] if r["scorable"]}
    comparisons = {}
    for mode, data in modes.items():
        paired = [r for r in data["public_control_rows"] if r["label_id"] in baseline]
        comparisons[mode] = {"baseline_scorable_faces": len(baseline),
            "still_scorable": sum(r["scorable"] for r in paired),
            "correct_on_baseline_controls": sum(r["correct"] is True for r in paired),
            "coverage_lost_ids": [r["label_id"] for r in paired if not r["scorable"]],
            "regressed_ids": [r["label_id"] for r in paired if baseline[r["label_id"]]["correct"] is True and r["correct"] is not True]}
    return comparisons


def evaluate(*, hand8_intake_zip, original_intake_zip, private_template_zip):
    import cv2
    from workspace.vision import public_meld_identity_sift as frozen
    from workspace.vision import public_meld_private_sift_loader as loader
    from workspace.vision.evaluate_existing_meld_intake import evaluate as evaluate_intake
    from workspace.vision.evaluate_bamboo8_reverse_probe import evaluate_reverse_probe

    pin = "references/vision/2026-10-03/hand8_s789_intake_v0_1.json"
    with ZipFile(hand8_intake_zip) as archive:
        if json.loads(archive.read("intake.json")) != json.loads(Path(pin).read_text()):
            raise ValueError("query metadata differs from pinned Hand 8 ledger")
    originals = frozen._sift_descriptors, loader._sift_descriptors, frozen._descriptor_similarity
    transformations = []

    def symmetric_descriptors(image):
        normalized, audit = normalize_single_face(image)
        transformations.append(audit)
        # No raw-image fallback: failed geometry must remain unscorable.
        return originals[0](normalized) if normalized is not None else None

    modes = {}
    for mode in ("direct_rectangle", "symmetric_existing_geometry"):
        extractor = originals[0] if mode == "direct_rectangle" else symmetric_descriptors
        with patch.object(frozen, "_sift_descriptors", extractor), patch.object(loader, "_sift_descriptors", extractor):
            hand8 = evaluate_intake(hand8_intake_zip, private_template_zip, include_group_rankings=True)
            original = evaluate_intake(original_intake_zip, private_template_zip)
            reverse = evaluate_reverse_probe(intake_zip=original_intake_zip, private_template_zip=private_template_zip)
        modes[mode] = {"hand8_face_summary": hand8["summary"], "hand8_group_summary": hand8["group_summary"],
            "hand8_face_rows": [{"frame": r["frame_index"], "face_index": r["face_index"],
                "expected": r["reviewed_candidate_tile"], "top1": r["modes"]["1"]["ranking"]["top1_tile"]} for r in hand8["faces"]],
            "original_intake_summary": original["summary"], "reverse_summary": reverse["summary"],
            "public_control_rows": [{"label_id": r["label_id"], "expected": r["expected_tile"],
                "scorable": r["modes"]["baseline"]["expected_class_scorable"],
                "top1": r["modes"]["baseline"]["ranking"]["top1_tile"],
                "correct": r["modes"]["baseline"]["top1_correct_when_scorable"]} for r in reverse["rows"]],
            "input_sha256": reverse["input_sha256"]}
    if (frozen._sift_descriptors, loader._sift_descriptors, frozen._descriptor_similarity) != originals:
        raise RuntimeError("frozen callbacks not restored")
    comparisons = compare_controls(modes)
    candidate = comparisons["symmetric_existing_geometry"]
    return {"schema_version": "sift_symmetric_geometry_probe_dev_v0_1", "modes": modes,
        "cross_mode_public_controls": comparisons,
        "transform_calls_not_unique_faces": len(transformations),
        "failed_transform_calls": sum(r["failed"] for r in transformations),
        "transformation_geometry_signatures_not_unique_faces": [
            {"geometry": json.loads(signature), "call_count": count}
            for signature, count in sorted(Counter(json.dumps(r, sort_keys=True) for r in transformations).items())],
        "query_ledger_sha256": hashlib.sha256(Path(pin).read_bytes()).hexdigest(),
        "opencv_version": cv2.__version__,
        "transform": "existing normalize_public_meld_crop on manually split single faces, canonical height 96",
        "role_symmetry": "public/private/experimental references and all queries use same extractor",
        "group_split_pipeline_equivalence_verified": False,
        "single_face_stack_output_used": False, "raw_fallback_on_geometry_failure": False,
        "scorer_changed": False, "thresholds_changed": False, "descriptor_dedup_applied": False,
        "identity_inset_applied": False, "parameter_search_performed": False,
        "frozen_callbacks_restored": True,
        "candidate_decision": "reject_due_to_control_regression_or_coverage_loss" if candidate["regressed_ids"] or candidate["coverage_lost_ids"] else "development_only_no_promotion",
        "previously_inspected": True, "blind_validation": False,
        "runtime_integration": False, "formal_promotion_evidence": False,
        "safe_for_runtime": False, "safe_for_hint": False, "safe_for_executor": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("hand8-intake-zip", "original-intake-zip", "private-template-zip", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    report = evaluate(hand8_intake_zip=args.hand8_intake_zip,
        original_intake_zip=args.original_intake_zip, private_template_zip=args.private_template_zip)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"controls": report["cross_mode_public_controls"],
        "hand8": {k: v["hand8_face_summary"] for k, v in report["modes"].items()},
        "decision": report["candidate_decision"]}))


if __name__ == "__main__":
    main()
