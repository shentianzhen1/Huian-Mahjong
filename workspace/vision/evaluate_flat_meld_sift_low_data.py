"""Inspected FLAT low-data ranking diagnostic; strict gates stay unchanged.

The one-other-original-match path is explicitly a separate offline diagnostic,
not the frozen two-other-match SIFT candidate and not a Runtime acceptance gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def evaluate_low_data_flat(
    *, repository_root: str | Path = ".", private_template_zip: str | Path,
) -> dict:
    from PIL import Image
    from workspace.vision.public_identity_labels import load_public_identity_manifest
    from workspace.vision.public_meld_identity_sift import build_public_meld_sift_bank, rank_public_meld_sift
    from workspace.vision.public_meld_private_sift_loader import augment_public_meld_sift_bank_from_private_zip
    from workspace.vision.public_meld_synthetic_transfer import _regular_player_meld_samples, _pixel_bbox
    from workspace.vision.public_meld_face_segmentation import prepare_public_meld_faces
    from workspace.vision.public_meld_group_identity_decoder import rank_regular_public_meld_identity
    from workspace.vision.public_tile_detector import PublicGeometryCandidate

    root = Path(repository_root).resolve()
    bank = build_public_meld_sift_bank(
        load_public_identity_manifest(root / "references/vision/2026-09-22/public_identity_labels_v0_1.json"),
        root, root / "references/vision/2026-09-24/public_identity_source_groups.development.json",
    )
    bank, loaded = augment_public_meld_sift_bank_from_private_zip(
        bank, private_zip_path=private_template_zip, repository_root=root,
        recovery_result_path=root / "references/vision/2026-10-02/public_meld_private_recovery_result_v0_3.json",
    )
    samples = _regular_player_meld_samples(json.loads(
        (root / "references/vision/2026-09-22/public_detector_calibration_v0_1.json").read_text()
    ))
    rows = []
    for sample in samples:
        path = (root / sample["image_path"]).resolve()
        if root not in path.parents or hashlib.sha256(path.read_bytes()).hexdigest() != sample["image_sha256"]:
            raise ValueError("reviewed query path or SHA mismatch")
        with Image.open(path) as source:
            image = source.convert("RGB")
        group = PublicGeometryCandidate(
            pixel_bbox=_pixel_bbox(sample["bbox"], image.size), normalized_bbox=tuple(sample["bbox"]),
            geometry_kind="bottom_group", confidence=1., fill_ratio=1.,
            frame=sample.get("frame_index"), session=sample["source_session"],
        )
        prepared = prepare_public_meld_faces(image, group)
        row = {"sample_id": sample["sample_id"], "expected_tiles": sample["expected_tiles"],
               "geometry": prepared.geometry.stack_state, "split_count": len(prepared.face_images), "modes": {}}
        for mode, support in (("strict_two_other_matches", 2), ("offline_one_other_match_diagnostic", 1)):
            ranks = [rank_public_meld_sift(
                bank, face, source_session=sample["source_session"], source_sha256=sample["source_sha256"],
                minimum_other_match_groups=support, include_class_scores=True,
            ) for face in prepared.face_images]
            scores = [rank["class_scores"] for rank in ranks]
            expected_classes = set(sample["expected_tiles"])
            # Truth is used only for evaluation, not for class selection/ranking.
            coverage = len(scores) == 3 and all(expected_classes <= set(face) for face in scores)
            decoded = rank_regular_public_meld_identity(scores) if len(scores) == 3 else None
            tiles = decoded.top_tiles if decoded else None
            row["modes"][mode] = {
                "minimum_other_original_matches": support,
                "face_top1": [rank["top1_tile"] for rank in ranks],
                "eligible_classes_by_face": [sorted(face) for face in scores],
                "expected_group_classes_all_scorable": coverage,
                "ranked_group": list(tiles) if tiles else None,
                "ranked_group_matches_reviewed_truth": bool(tiles and sorted(tiles) == sorted(sample["expected_tiles"])),
                "group_identity_status": "UNKNOWN", "safe_for_runtime": False,
            }
        rows.append(row)
    summary = {}
    for mode in ("strict_two_other_matches", "offline_one_other_match_diagnostic"):
        eligible = [row["modes"][mode] for row in rows if row["modes"][mode]["expected_group_classes_all_scorable"]]
        summary[mode] = {"fully_scorable_reviewed_groups": len(eligible),
                         "correct_ranked_groups_among_scorable": sum(row["ranked_group_matches_reviewed_truth"] for row in eligible)}
    return {"schema_version": "flat_meld_sift_low_data_diagnostic_dev_v0_1", "group_count": len(rows),
            "private_template_load": loaded, "summary": summary, "rows": rows,
            "one_match_mode_is_frozen_candidate": False, "query_original_match_excluded": True,
            "query_exact_sha_excluded": True, "query_image_sha_verified": True,
            "previously_inspected": True, "blind_validation": False,
            "runtime_threshold_changed": False, "scorer_parameters_changed": False,
            "development_only": True, "formal_promotion_evidence": False,
            "safe_for_runtime": False, "safe_for_hint": False, "safe_for_executor": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--private-template-zip", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = evaluate_low_data_flat(repository_root=args.repository_root, private_template_zip=args.private_template_zip)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"]))


if __name__ == "__main__":
    main()
