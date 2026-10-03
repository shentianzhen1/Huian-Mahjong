"""One inspected within-Wan upper-half diagnostic, not 34-class recognition."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile


def evaluate_wan_probe(*, private_template_zip: str | Path, repository_root: str | Path = ".") -> dict:
    from PIL import Image
    from workspace.vision.public_identity_labels import load_public_identity_manifest, approved_labels, pixel_bbox
    from workspace.vision.public_meld_identity_sift import (
        build_public_meld_sift_bank, PublicMeldSiftBank, PublicMeldSiftTemplate,
        _sift_descriptors, rank_public_meld_sift,
    )
    from workspace.vision.public_meld_private_sift_loader import (
        augment_public_meld_sift_bank_from_private_zip, _matching_private_group,
    )
    from workspace.vision.public_meld_private_recovery_result import load_private_recovery_results, RecoveredPrivateTemplate
    from workspace.vision.public_meld_synthetic_transfer import _pixel_bbox
    from workspace.vision.public_meld_face_segmentation import prepare_public_meld_faces
    from workspace.vision.public_tile_detector import PublicGeometryCandidate
    from workspace.vision.public_meld_group_identity_decoder import rank_regular_public_meld_identity

    root = Path(repository_root).resolve()
    manifest = load_public_identity_manifest(root / "references/vision/2026-09-22/public_identity_labels_v0_1.json")
    bank = build_public_meld_sift_bank(manifest, root, root / "references/vision/2026-09-24/public_identity_source_groups.development.json")
    recovery_path = root / "references/vision/2026-10-02/public_meld_private_recovery_result_v0_3.json"
    bank, loaded = augment_public_meld_sift_bank_from_private_zip(
        bank, private_zip_path=private_template_zip, recovery_result_path=recovery_path, repository_root=root,
    )

    def upper(image):
        return image.crop((0, 0, image.width, max(1, image.height // 2)))

    records = []
    for label in approved_labels(manifest):
        if label.region != "public_meld" or not label.tile_id.startswith("M"):
            continue
        with Image.open(root / label.image_path) as source:
            image = source.convert("RGB")
        x, y, width, height = pixel_bbox(label, image.size)
        descriptors = _sift_descriptors(upper(image.crop((x, y, x + width, y + height))))
        if descriptors is not None:
            source = bank.sources[label.source_session]
            records.append(PublicMeldSiftTemplate(label.tile_id, label.source_session, label.source_sha256, source.match_group, descriptors))

    recovered = [item for item in load_private_recovery_results(recovery_path).values()
                 if isinstance(item, RecoveredPrivateTemplate)]
    if not recovered:
        raise ValueError("verified recovered private templates required")
    # The existing loader above verifies the pinned manifest and all loaded crop
    # hashes. Repeat crop-byte verification before this alternate feature read.
    with ZipFile(private_template_zip) as archive:
        groups = json.loads(archive.read(recovered[0].private_label_manifest_name))["groups"]
        for item in recovered:
            group = _matching_private_group(tuple(groups), item)
            session = "private_recovered_" + item.recovery_id
            for index, face in enumerate(group["faces"]):
                tile = item.tile_ids[index]
                if not tile.startswith("M"):
                    continue
                raw = archive.read("approved_faces/" + face["crop_file"])
                if hashlib.sha256(raw).hexdigest() != item.crop_sha256[index]:
                    raise ValueError("private numerator crop hash mismatch")
                with Image.open(io.BytesIO(raw)) as source:
                    descriptors = _sift_descriptors(upper(source.convert("RGB")))
                if descriptors is not None:
                    records.append(PublicMeldSiftTemplate(tile, session, item.source_sha256, item.match_group, descriptors))

    calibration = json.loads((root / "references/vision/2026-09-22/public_detector_calibration_v0_1.json").read_text())
    sample = next(row for row in calibration["samples"] if row["sample_id"] == "b389_player_chi_m456_035s")
    path = (root / sample["image_path"]).resolve()
    if root not in path.parents or hashlib.sha256(path.read_bytes()).hexdigest() != sample["image_sha256"]:
        raise ValueError("reviewed query image hash mismatch")
    with Image.open(path) as source:
        image = source.convert("RGB")
    group = PublicGeometryCandidate(pixel_bbox=_pixel_bbox(sample["bbox"], image.size),
        normalized_bbox=tuple(sample["bbox"]), geometry_kind="bottom_group", confidence=1., fill_ratio=1.,
        frame=sample.get("frame_index"), session=sample["source_session"])
    faces = prepare_public_meld_faces(image, group).face_images
    if len(faces) != 3:
        raise ValueError("reviewed FLAT query must yield three faces")
    numeral_bank = PublicMeldSiftBank(bank.sources, tuple(records))
    modes = {}
    for mode, selected_bank, transform in (
        ("whole_face_all_classes", bank, lambda face: face),
        ("whole_face_wan_only", PublicMeldSiftBank(bank.sources, tuple(t for t in bank.templates if t.tile_id.startswith("M"))), lambda face: face),
        ("upper_half_wan_only", numeral_bank, upper),
    ):
        ranks = [rank_public_meld_sift(selected_bank, transform(face), source_session=sample["source_session"],
            source_sha256=sample["source_sha256"], minimum_other_match_groups=1, include_class_scores=True) for face in faces]
        modes[mode] = {"face_rankings": ranks,
                       "group_ranking": rank_regular_public_meld_identity([row["class_scores"] for row in ranks]).to_dict()}
    return {"schema_version": "wan_numeral_upper_half_probe_dev_v0_1", "sample_id": sample["sample_id"],
        "reviewed_expected_tiles": sample["expected_tiles"], "modes": modes, "upper_crop_fraction": .5,
        "crop_ratio_search_performed": False, "private_template_load": loaded,
        "within_suit_only": True, "suit_recognition_measured": False, "scorer_parameters_changed": False,
        "minimum_other_original_matches": 1, "one_match_mode_is_frozen_candidate": False,
        "query_original_match_excluded": True, "query_exact_sha_excluded": True,
        "previously_inspected": True, "blind_validation": False,
        "runtime_threshold_changed": False, "runtime_integration": False,
        "formal_promotion_evidence": False, "safe_for_runtime": False, "safe_for_hint": False, "safe_for_executor": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--private-template-zip", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = evaluate_wan_probe(private_template_zip=args.private_template_zip, repository_root=args.repository_root)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({name: {"face_top1": [row["top1_tile"] for row in mode["face_rankings"]],
                            "group_top": mode["group_ranking"]["top_tiles"]} for name, mode in report["modes"].items()}))


if __name__ == "__main__":
    main()
