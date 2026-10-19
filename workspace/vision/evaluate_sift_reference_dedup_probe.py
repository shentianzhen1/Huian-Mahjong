"""One fixed offline match-aggregation diagnostic; frozen SIFT stays unchanged."""
from __future__ import annotations

import argparse
from collections import Counter
import io
import json
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile


def unique_reference_distances(matches):
    """A reference descriptor contributes only its smallest matched distance."""
    best = {}
    for match in matches:
        best[match.trainIdx] = min(best.get(match.trainIdx, float("inf")), float(match.distance))
    return [best[index] for index in sorted(best)]


def match_audit(first, second):
    import cv2
    import numpy as np
    from workspace.vision import public_meld_identity_sift as frozen

    if first is None or second is None or len(first) < 2 or len(second) < 2:
        return None
    matcher = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
    pairs = matcher.knnMatch(first, second, k=frozen.SIFT_KNN_K)
    selected = [pair[0] for pair in pairs if len(pair) == frozen.SIFT_KNN_K
                and pair[0].distance < frozen.SIFT_RATIO_TEST * pair[1].distance]
    ratio_count = len(selected)
    if not selected:
        selected = sorted(matcher.match(first, second), key=lambda m: m.distance)[:frozen.SIFT_FALLBACK_RAW_MATCHES]
    if not selected:
        return None
    old = [float(m.distance) for m in selected]
    new = unique_reference_distances(selected)
    return {"query_descriptor_count": len(first), "reference_descriptor_count": len(second),
        "ratio_match_count": ratio_count, "raw_fallback_used": ratio_count == 0,
        "counted_matches_before": len(old), "unique_reference_descriptors": len(new),
        "maximum_query_matches_to_one_reference": max(Counter(m.trainIdx for m in selected).values()),
        "baseline_score": float(len(old) / (1 + np.mean(old))),
        "deduplicated_score": float(len(new) / (1 + np.mean(new)))}


def unique_reference_similarity(first, second):
    audit = match_audit(first, second)
    return audit["deduplicated_score"] if audit else None


def evaluate(*, hand8_intake_zip, original_intake_zip, private_template_zip):
    import cv2
    from PIL import Image
    from workspace.vision import public_meld_identity_sift as frozen
    from workspace.vision.public_identity_labels import load_public_identity_manifest, approved_labels, pixel_bbox
    from workspace.vision.evaluate_existing_meld_intake import evaluate as evaluate_intake
    from workspace.vision.evaluate_bamboo8_reverse_probe import evaluate_reverse_probe

    # The query ledger is immutable for this experiment, not a crop search.
    pinned = json.loads(Path("references/vision/2026-10-03/hand8_s789_intake_v0_1.json").read_text())
    with ZipFile(hand8_intake_zip) as archive:
        if json.loads(archive.read("intake.json")) != pinned:
            raise ValueError("Hand 8 intake differs from pinned query ledger")
        row = next(r for r in pinned["faces"] if r["frame_index"] == 4800 and r["face_index"] == 2)
        raw = archive.read(row["crop_file"])
        import hashlib
        if hashlib.sha256(raw).hexdigest() != row["crop_sha256"]:
            raise ValueError("representative query crop SHA mismatch")
        with Image.open(io.BytesIO(raw)) as image:
            query = frozen._sift_descriptors(image)
    labels = approved_labels(load_public_identity_manifest("references/vision/2026-09-22/public_identity_labels_v0_1.json"))
    audit = {}
    for tile in ("S9", "S2"):
        label = next(l for l in labels if l.region == "public_meld" and l.tile_id == tile)
        with Image.open(label.image_path) as source:
            image = source.convert("RGB")
        x, y, w, h = pixel_bbox(label, image.size)
        audit[tile] = {"reference_label_id": label.label_id,
            "match_audit": match_audit(query, frozen._sift_descriptors(image.crop((x, y, x + w, y + h))))}
    modes = {}
    original_callback = frozen._descriptor_similarity
    for mode in ("frozen_baseline", "unique_reference_descriptor"):
        callback = original_callback if mode == "frozen_baseline" else unique_reference_similarity
        # Context restoration is mandatory. Only this development harness patches
        # the scorer; no production module or default bank is edited.
        with patch.object(frozen, "_descriptor_similarity", callback):
            forward = evaluate_intake(hand8_intake_zip, private_template_zip, include_group_rankings=True)
            original = evaluate_intake(original_intake_zip, private_template_zip)
            reverse = evaluate_reverse_probe(intake_zip=original_intake_zip, private_template_zip=private_template_zip)
        modes[mode] = {
            "hand8_face_summary": forward["summary"], "hand8_group_summary": forward["group_summary"],
            "hand8_face_rows": [{"frame_index": r["frame_index"], "expected": r["reviewed_candidate_tile"],
                "top1": r["modes"]["1"]["ranking"]["top1_tile"]} for r in forward["faces"]],
            "hand8_group_rows": [{"frame_index": g["frame_index"], "ranked_tiles": g["decoder"]["top_tiles"],
                "margin": g["decoder"]["margin"]} for g in forward["group_rankings"] if g["minimum_other_original_matches"] == 1],
            "original_intake_summary": original["summary"], "reverse_public_summary": reverse["summary"],
            "input_sha256": reverse["input_sha256"], "match_aggregation_changed": mode != "frozen_baseline"}
    if frozen._descriptor_similarity is not original_callback:
        raise RuntimeError("frozen scorer callback not restored")
    return {"schema_version": "sift_reference_descriptor_dedup_probe_dev_v0_1", "modes": modes,
        "representative_frame4800_match_audit": audit, "opencv_version": cv2.__version__,
        "query_source_sha256": pinned["faces"][0]["source_sha256"],
        "query_reference_parameters_changed": False, "descriptor_extraction_changed": False,
        "ratio_threshold_changed": False, "fallback_selection_changed": False,
        "experimental_change": "deduplicate selected matches by trainIdx, keep minimum distance",
        "spatial_consistency_checked": False, "coordinate_duplicate_orientations_collapsed": False,
        "frozen_scorer_restored": True, "previously_inspected": True, "blind_validation": False,
        "runtime_integration": False, "formal_promotion_evidence": False,
        "safe_for_runtime": False, "safe_for_hint": False, "safe_for_executor": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hand8-intake-zip", required=True)
    parser.add_argument("--original-intake-zip", required=True)
    parser.add_argument("--private-template-zip", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = evaluate(hand8_intake_zip=args.hand8_intake_zip, original_intake_zip=args.original_intake_zip,
        private_template_zip=args.private_template_zip)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({mode: {"faces": r["hand8_face_summary"], "groups": r["hand8_group_summary"]} for mode, r in report["modes"].items()}))


if __name__ == "__main__":
    main()
