"""Fixed three-face S8 reference experiment, with source-disjoint controls.

The harvested frame was locked before this experiment. Its assistant-reviewed,
manual crops are experimental references only, never default-bank templates.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile


def evaluate_reverse_probe(*, intake_zip, private_template_zip, repository_root="."):
    from PIL import Image
    from workspace.vision.public_identity_labels import load_public_identity_manifest, approved_labels, pixel_bbox
    from workspace.vision.public_identity_shadow_v0_2 import SourceGroup
    from workspace.vision.public_meld_identity_sift import (
        build_public_meld_sift_bank, rank_public_meld_sift, PublicMeldSiftBank, PublicMeldSiftTemplate, _sift_descriptors,
    )
    from workspace.vision.public_meld_private_sift_loader import augment_public_meld_sift_bank_from_private_zip

    root = Path(repository_root)
    label_path = "references/vision/2026-09-22/public_identity_labels_v0_1.json"
    manifest = load_public_identity_manifest(root / label_path)
    bank = build_public_meld_sift_bank(manifest, root, root / "references/vision/2026-09-24/public_identity_source_groups.development.json")
    bank, loaded = augment_public_meld_sift_bank_from_private_zip(bank, private_zip_path=private_template_zip,
        recovery_result_path=root / "references/vision/2026-10-02/public_meld_private_recovery_result_v0_3.json", repository_root=root)
    spec_path = "references/vision/2026-10-03/existing_video_meld_face_harvest_spec_v0_1.json"
    pinned_spec = json.loads((root / spec_path).read_text())
    sources = dict(bank.sources)
    extra = []
    reference_rows = []
    with ZipFile(intake_zip) as archive:
        intake = json.loads(archive.read("intake.json"))
        pinned_intake = json.loads((root / "references/vision/2026-10-03/existing_video_meld_face_intake_v0_1.json").read_text())
        if intake != pinned_intake:
            raise ValueError("intake metadata differs from repository pixel/hash pin")
        if intake["spec"] != pinned_spec:
            raise ValueError("intake source spec differs from repository pin")
        aliases = set(pinned_spec["excluded_same_match_aliases"])
        canonical = pinned_spec["conservative_original_match_group"]
        # Collapse the older first-hand/eight-hand names before either direction.
        sources = {key: SourceGroup(s.session, s.source_sha256, canonical if s.match_group in aliases else s.match_group)
                   for key, s in sources.items()}
        templates = tuple(PublicMeldSiftTemplate(t.tile_id, t.source_session, t.source_sha256,
            canonical if t.match_group in aliases else t.match_group, t.descriptors) for t in bank.templates)
        for source in pinned_spec["sources"]:
            sources[source["source_session"]] = SourceGroup(source["source_session"], source["source_sha256"], canonical)
        selected = [f for f in intake["faces"] if f["group_id"] == "hand7_bamboo8" and f["frame_index"] == 1800]
        if len(selected) != 3 or {f["face_index"] for f in selected} != {0, 1, 2}:
            raise ValueError("fixed frame must contain exactly three reviewed faces")
        pinned_source = next(s for s in pinned_spec["sources"] if s["source_session"] == selected[0]["source_session"])
        pinned_group = next(g for g in pinned_source["groups"] if g["group_id"] == "hand7_bamboo8")
        for face in selected:
            if face["source_sha256"] != pinned_source["source_sha256"] or face["bbox"] != pinned_group["face_bboxes"][face["face_index"]] or face["reviewed_candidate_tile"] != "S8" or face["match_group"] != canonical:
                raise ValueError("reference identity/lineage/ROI differs from fixed spec")
            raw = archive.read(face["crop_file"])
            if hashlib.sha256(raw).hexdigest() != face["crop_sha256"]:
                raise ValueError("experimental reference crop SHA mismatch")
            with Image.open(io.BytesIO(raw)) as image:
                descriptors = _sift_descriptors(image)
            if descriptors is None:
                raise ValueError("experimental reference lacks descriptors")
            extra.append(PublicMeldSiftTemplate("S8", face["source_session"], face["source_sha256"], canonical, descriptors))
            reference_rows.append({key: face[key] for key in ("group_id", "frame_index", "face_index", "source_sha256", "crop_sha256", "match_group")})
    baseline = PublicMeldSiftBank(sources, templates)
    augmented = PublicMeldSiftBank(sources, templates + tuple(extra))
    rows = []
    for label in approved_labels(manifest):
        if label.region != "public_meld":
            continue
        with Image.open(root / label.image_path) as source:
            image = source.convert("RGB")
        x, y, w, h = pixel_bbox(label, image.size)
        face = image.crop((x, y, x + w, y + h))
        row = {"label_id": label.label_id, "expected_tile": label.tile_id,
               "query_match_group": sources[label.source_session].match_group, "modes": {}}
        for mode, selected_bank in (("baseline", baseline), ("fixed_s8_experimental_reference", augmented)):
            rank = rank_public_meld_sift(selected_bank, face, source_session=label.source_session,
                source_sha256=label.source_sha256, minimum_other_match_groups=1, include_class_scores=True)
            scorable = label.tile_id in rank.pop("class_scores")
            row["modes"][mode] = {"ranking": rank, "expected_class_scorable": scorable,
                "top1_correct_when_scorable": rank["top1_tile"] == label.tile_id if scorable else None}
        rows.append(row)
    paired = [r for r in rows if all(m["expected_class_scorable"] for m in r["modes"].values())]
    new = [r for r in rows if not r["modes"]["baseline"]["expected_class_scorable"] and r["modes"]["fixed_s8_experimental_reference"]["expected_class_scorable"]]
    summary = {"public_face_rows": len(rows), "paired_scorable_faces": len(paired),
        "baseline_correct_on_paired": sum(r["modes"]["baseline"]["top1_correct_when_scorable"] for r in paired),
        "augmented_correct_on_paired": sum(r["modes"]["fixed_s8_experimental_reference"]["top1_correct_when_scorable"] for r in paired),
        "newly_supported_faces": len(new),
        "newly_supported_correct": sum(r["modes"]["fixed_s8_experimental_reference"]["top1_correct_when_scorable"] for r in new),
        "regressed_label_ids": [r["label_id"] for r in paired if r["modes"]["baseline"]["top1_correct_when_scorable"] and not r["modes"]["fixed_s8_experimental_reference"]["top1_correct_when_scorable"]]}
    return {"schema_version": "bamboo8_fixed_reference_reverse_probe_dev_v0_1", "summary": summary,
        "reference_rows": reference_rows, "rows": rows, "private_template_load": loaded,
        "input_sha256": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in (
            label_path, spec_path, "references/vision/2026-10-03/existing_video_meld_face_intake_v0_1.json",
            "references/vision/2026-09-24/public_identity_source_groups.development.json",
            "references/vision/2026-10-02/public_meld_private_recovery_result_v0_3.json")},
        "reference_selection": "all three faces of already-reviewed frame1800; no frame/crop/parameter search",
        "experimental_reference_original_match_count": 1, "reference_label_authority": "assistant_visual_review",
        "same_match_aliases_collapsed": sorted(aliases), "minimum_other_original_matches": 1,
        "default_bank_modified": False, "scorer_parameters_changed": False, "blind_validation": False,
        "formal_promotion_evidence": False, "runtime_integration": False,
        "safe_for_runtime": False, "safe_for_hint": False, "safe_for_executor": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intake-zip", required=True)
    parser.add_argument("--private-template-zip", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = evaluate_reverse_probe(intake_zip=args.intake_zip, private_template_zip=args.private_template_zip)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"]))


if __name__ == "__main__":
    main()
