"""Single fixed 3x3 layout diagnostic; measure collateral ranking errors."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import patch


def spatial_descriptors(image):
    import cv2
    import numpy as np
    from workspace.vision import public_meld_identity_sift as frozen

    gray = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    gray = cv2.resize(gray, None, fx=frozen.SIFT_SCALE_FACTOR, fy=frozen.SIFT_SCALE_FACTOR, interpolation=cv2.INTER_CUBIC)
    gray = cv2.createCLAHE(clipLimit=frozen.SIFT_CLAHE_CLIP_LIMIT, tileGridSize=frozen.SIFT_CLAHE_TILE_GRID).apply(gray)
    keypoints, descriptors = cv2.SIFT_create(nfeatures=frozen.SIFT_NFEATURES).detectAndCompute(gray, None)
    if descriptors is None or len(descriptors) < 2:
        return None
    cells = np.array([[min(2, int(k.pt[0] / gray.shape[1] * 3)), min(2, int(k.pt[1] / gray.shape[0] * 3))]
                      for k in keypoints], dtype="float32")
    return np.column_stack((descriptors, cells)).astype("float32")


def spatial_similarity(first, second):
    import cv2
    import numpy as np
    from workspace.vision import public_meld_identity_sift as frozen
    from workspace.vision.evaluate_sift_reference_dedup_probe import unique_reference_distances

    if first is None or second is None or len(first) < 2 or len(second) < 2:
        return None
    if first.shape[1] != 130 or second.shape[1] != 130:
        raise ValueError("spatial diagnostic requires descriptor+cell arrays")
    mask = np.all(first[:, None, 128:] == second[None, :, 128:], axis=2).astype("uint8")
    matcher = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
    query, reference = first[:, :128].copy(), second[:, :128].copy()
    pairs = matcher.knnMatch(query, reference, k=frozen.SIFT_KNN_K, mask=mask)
    matches = [p[0] for p in pairs if len(p) == frozen.SIFT_KNN_K and p[0].distance < frozen.SIFT_RATIO_TEST * p[1].distance]
    if not matches:
        # The fallback obeys the same mask: never silently match another cell.
        matches = sorted(matcher.match(query, reference, mask=mask), key=lambda m: m.distance)[:frozen.SIFT_FALLBACK_RAW_MATCHES]
    distances = unique_reference_distances(matches)
    return float(len(distances) / (1 + np.mean(distances))) if distances else None


def evaluate(*, hand8_intake_zip, original_intake_zip, private_template_zip):
    import cv2
    from workspace.vision import public_meld_identity_sift as frozen
    from workspace.vision import public_meld_private_sift_loader as loader
    from workspace.vision.evaluate_existing_meld_intake import evaluate as evaluate_intake
    from workspace.vision.evaluate_bamboo8_reverse_probe import evaluate_reverse_probe
    from workspace.vision.evaluate_sift_reference_dedup_probe import unique_reference_similarity

    from zipfile import ZipFile
    import hashlib
    query_pin_path = "references/vision/2026-10-03/hand8_s789_intake_v0_1.json"
    with ZipFile(hand8_intake_zip) as archive:
        if json.loads(archive.read("intake.json")) != json.loads(Path(query_pin_path).read_text()):
            raise ValueError("query metadata differs from pinned Hand 8 ledger")
    originals = frozen._sift_descriptors, loader._sift_descriptors, frozen._descriptor_similarity
    modes = {}
    for mode in ("frozen_baseline", "reference_dedup", "fixed_3x3_grid_reference_dedup"):
        extractor = spatial_descriptors if mode.startswith("fixed") else originals[0]
        scorer = spatial_similarity if mode.startswith("fixed") else unique_reference_similarity if mode == "reference_dedup" else originals[2]
        with patch.object(frozen, "_sift_descriptors", extractor), patch.object(loader, "_sift_descriptors", extractor), patch.object(frozen, "_descriptor_similarity", scorer):
            hand8 = evaluate_intake(hand8_intake_zip, private_template_zip, include_group_rankings=True)
            hand7 = evaluate_intake(original_intake_zip, private_template_zip)
            reverse = evaluate_reverse_probe(intake_zip=original_intake_zip, private_template_zip=private_template_zip)
        controls = [{"label_id": r["label_id"], "expected": r["expected_tile"],
                     "scorable": r["modes"]["baseline"]["expected_class_scorable"],
                     "top1": r["modes"]["baseline"]["ranking"]["top1_tile"],
                     "correct_when_scorable": r["modes"]["baseline"]["top1_correct_when_scorable"]}
                    for r in reverse["rows"]]
        modes[mode] = {"hand8_face_summary": hand8["summary"], "hand8_group_summary": hand8["group_summary"],
            "hand8_face_rows": [{"frame": r["frame_index"], "expected": r["reviewed_candidate_tile"], "top1": r["modes"]["1"]["ranking"]["top1_tile"]} for r in hand8["faces"]],
            "hand7_face_summary": hand7["summary"], "reverse_summary": reverse["summary"],
            "public_control_rows": controls, "input_sha256": reverse["input_sha256"]}
    if (frozen._sift_descriptors, loader._sift_descriptors, frozen._descriptor_similarity) != originals:
        raise RuntimeError("frozen callbacks not restored")
    baseline = {r["label_id"]: r for r in modes["frozen_baseline"]["public_control_rows"] if r["scorable"]}
    cross_mode = {}
    for mode, data in modes.items():
        paired = [r for r in data["public_control_rows"] if r["label_id"] in baseline]
        cross_mode[mode] = {"baseline_scorable_control_faces": len(baseline),
            "still_scorable": sum(r["scorable"] for r in paired),
            "correct_on_baseline_controls": sum(r["correct_when_scorable"] is True for r in paired),
            "coverage_lost_ids": [r["label_id"] for r in paired if not r["scorable"]],
            "regressed_ids": [r["label_id"] for r in paired if baseline[r["label_id"]]["correct_when_scorable"] and r["scorable"] and not r["correct_when_scorable"]]}
    return {"schema_version": "sift_fixed_spatial_grid_probe_dev_v0_1", "modes": modes,
        "cross_mode_public_controls": cross_mode, "query_ledger_sha256": hashlib.sha256(Path(query_pin_path).read_bytes()).hexdigest(),
        "opencv_version": cv2.__version__, "fixed_grid_rows": 3, "fixed_grid_columns": 3,
        "grid_search_performed": False, "mask_applied_to_ratio_and_fallback": True,
        "query_crops_changed": False, "thresholds_changed": False, "frozen_callbacks_restored": True,
        "candidate_decision": "do_not_adopt_grid_candidate_due_to_public_control_regressions",
        "previously_inspected": True, "blind_validation": False, "runtime_integration": False,
        "formal_promotion_evidence": False, "safe_for_runtime": False, "safe_for_hint": False, "safe_for_executor": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hand8-intake-zip", required=True)
    parser.add_argument("--original-intake-zip", required=True)
    parser.add_argument("--private-template-zip", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = evaluate(hand8_intake_zip=args.hand8_intake_zip, original_intake_zip=args.original_intake_zip, private_template_zip=args.private_template_zip)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["cross_mode_public_controls"]))


if __name__ == "__main__":
    main()
