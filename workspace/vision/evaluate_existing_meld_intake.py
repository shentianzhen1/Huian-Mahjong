"""Rank harvested faces against the unchanged bank; never add query crops to it."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile


def evaluate(intake_zip, private_template_zip, repository_root="."):
    from PIL import Image
    from workspace.vision.public_identity_labels import load_public_identity_manifest
    from workspace.vision.public_identity_shadow_v0_2 import SourceGroup
    from workspace.vision.public_meld_identity_sift import build_public_meld_sift_bank, rank_public_meld_sift, PublicMeldSiftBank
    from workspace.vision.public_meld_private_sift_loader import augment_public_meld_sift_bank_from_private_zip

    root = Path(repository_root)
    manifest = load_public_identity_manifest(root / "references/vision/2026-09-22/public_identity_labels_v0_1.json")
    bank = build_public_meld_sift_bank(manifest, root, root / "references/vision/2026-09-24/public_identity_source_groups.development.json")
    bank, loaded = augment_public_meld_sift_bank_from_private_zip(bank, private_zip_path=private_template_zip,
        recovery_result_path=root / "references/vision/2026-10-02/public_meld_private_recovery_result_v0_3.json", repository_root=root)
    rows = []
    with ZipFile(intake_zip) as archive:
        intake = json.loads(archive.read("intake.json"))
        aliases = set(intake["spec"]["excluded_same_match_aliases"])
        aliases.add(intake["spec"]["conservative_original_match_group"])
        sources = dict(bank.sources)
        for source in intake["spec"]["sources"]:
            sources[source["source_session"]] = SourceGroup(source["source_session"], source["source_sha256"], intake["spec"]["conservative_original_match_group"])
        # Explicit alias filtering also excludes older first-hand-only registries.
        bank = PublicMeldSiftBank(sources, tuple(t for t in bank.templates if t.match_group not in aliases))
        for face in intake["faces"]:
            raw = archive.read(face["crop_file"])
            if hashlib.sha256(raw).hexdigest() != face["crop_sha256"]:
                raise ValueError("intake crop SHA mismatch")
            with Image.open(io.BytesIO(raw)) as image:
                modes = {}
                for minimum in (1, 2):
                    rank = rank_public_meld_sift(bank, image.convert("RGB"), source_session=face["source_session"],
                        source_sha256=face["source_sha256"], minimum_other_match_groups=minimum, include_class_scores=True)
                    supported = face["reviewed_candidate_tile"] in rank["class_scores"]
                    # Qualification requires class scores, but the public intake
                    # report only needs the winner, margin and support outcome.
                    rank.pop("class_scores")
                    modes[str(minimum)] = {"ranking": rank, "reviewed_candidate_scorable": supported,
                        "matches_reviewed_candidate_when_scorable": rank["top1_tile"] == face["reviewed_candidate_tile"] if supported else None}
            rows.append({"group_id": face["group_id"], "frame_index": face["frame_index"], "face_index": face["face_index"],
                "crop_sha256": face["crop_sha256"], "reviewed_candidate_tile": face["reviewed_candidate_tile"], "modes": modes})
    summary = {}
    for minimum in ("1", "2"):
        summary[minimum] = {tile: {"face_count": len(selected := [r for r in rows if r["reviewed_candidate_tile"] == tile]),
            "scorable_faces": sum(r["modes"][minimum]["reviewed_candidate_scorable"] for r in selected),
            "matching_candidate_faces": sum(r["modes"][minimum]["matches_reviewed_candidate_when_scorable"] is True for r in selected)}
            for tile in sorted({r["reviewed_candidate_tile"] for r in rows})}
    return {"schema_version": "existing_meld_intake_frozen_sift_probe_dev_v0_1", "summary": summary, "faces": rows,
        "input_sha256": {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in (
            "references/vision/2026-09-22/public_identity_labels_v0_1.json",
            "references/vision/2026-09-24/public_identity_source_groups.development.json",
            "references/vision/2026-10-02/public_meld_private_recovery_result_v0_3.json")},
        "private_template_load": loaded, "query_crops_added_to_bank": False, "same_match_aliases_excluded": sorted(aliases),
        "manual_crops": True, "assistant_review_not_user_truth": True, "original_query_match_count": 1,
        "parameters_changed": False, "blind_validation": False, "formal_promotion_evidence": False,
        "runtime_integration": False, "safe_for_runtime": False, "safe_for_hint": False, "safe_for_executor": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intake-zip", required=True)
    parser.add_argument("--private-template-zip", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = evaluate(args.intake_zip, args.private_template_zip)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"]))


if __name__ == "__main__":
    main()
