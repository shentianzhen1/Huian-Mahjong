"""Check fixed raw-face seam context on other inspected groups from one match."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile


def evaluate(*, video_dir, intake_zip, private_template_zip):
    import cv2
    from PIL import Image
    from workspace.vision.evaluate_sift_symmetric_geometry_probe import normalize_single_face
    from workspace.vision.public_identity_labels import load_public_identity_manifest
    from workspace.vision.public_identity_shadow_v0_2 import SourceGroup
    from workspace.vision.public_meld_identity_sift import (
        PublicMeldSiftBank, build_public_meld_sift_bank, rank_public_meld_sift,
    )
    from workspace.vision.public_meld_private_sift_loader import augment_public_meld_sift_bank_from_private_zip

    root = Path(".")
    pin_path = root / "references/vision/2026-10-03/existing_video_meld_face_intake_v0_1.json"
    pin = json.loads(pin_path.read_text())
    spec = pin["spec"]
    manifest = load_public_identity_manifest(root / "references/vision/2026-09-22/public_identity_labels_v0_1.json")
    bank = build_public_meld_sift_bank(manifest, root,
        root / "references/vision/2026-09-24/public_identity_source_groups.development.json")
    bank, loaded = augment_public_meld_sift_bank_from_private_zip(bank,
        private_zip_path=private_template_zip,
        recovery_result_path=root / "references/vision/2026-10-02/public_meld_private_recovery_result_v0_3.json",
        repository_root=root)
    aliases = set(spec["excluded_same_match_aliases"])
    sources = dict(bank.sources)
    for source in spec["sources"]:
        sources[source["source_session"]] = SourceGroup(source["source_session"],
            source["source_sha256"], spec["conservative_original_match_group"])
    bank = PublicMeldSiftBank(sources, tuple(t for t in bank.templates if t.match_group not in aliases))
    rows = []
    with ZipFile(intake_zip) as archive:
        if json.loads(archive.read("intake.json")) != pin:
            raise ValueError("private intake differs from pinned ledger")
        indexed = {(f["group_id"], f["frame_index"], f["face_index"]): f for f in pin["faces"]}
        for source in spec["sources"]:
            video = Path(video_dir) / source["filename"]
            if hashlib.sha256(video.read_bytes()).hexdigest() != source["source_sha256"]:
                raise ValueError("pinned video source SHA mismatch")
            cap = cv2.VideoCapture(str(video))
            if not cap.isOpened():
                raise ValueError("cannot open pinned video")
            try:
                for group in source["groups"]:
                    boxes = group["face_bboxes"]
                    left, top = min(b[0] for b in boxes), min(b[1] for b in boxes)
                    right = max(b[0] + b[2] for b in boxes)
                    bottom = max(b[1] + b[3] for b in boxes)
                    width = right - left
                    boundaries = [round(width * i / 3) for i in range(4)]
                    for frame in group["frame_indices"]:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
                        ok, bgr = cap.read()
                        if not ok or int(cap.get(cv2.CAP_PROP_POS_FRAMES)) != frame + 1:
                            raise ValueError("pinned frame decode mismatch")
                        image = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
                        for i, box in enumerate(boxes):
                            face = indexed[(group["group_id"], frame, i)]
                            crop_raw = archive.read(face["crop_file"])
                            if hashlib.sha256(crop_raw).hexdigest() != face["crop_sha256"]:
                                raise ValueError("private face SHA mismatch")
                            with Image.open(io.BytesIO(crop_raw)) as stored:
                                direct = stored.convert("RGB")
                            x, y, w, h = box
                            if direct.tobytes() != image.crop((x, y, x+w, y+h)).tobytes():
                                raise ValueError("private face differs from decoded source pixels")
                            candidates = {
                                "pinned_direct": direct,
                                "raw_equal_thirds": image.crop((left+boundaries[i], top,
                                    left+boundaries[i+1], bottom)),
                                "raw_equal_thirds_two_pixel_seam_context": image.crop((
                                    left+max(0, boundaries[i]-(2 if i else 0)), top,
                                    left+min(width, boundaries[i+1]+(2 if i < 2 else 0)), bottom)),
                            }
                            modes = {}
                            for mode, query in candidates.items():
                                normalized, _ = normalize_single_face(query)
                                if normalized is None:
                                    modes[mode] = {"scorable": False, "top1": None, "correct": None,
                                        "reason": "single_face_normalization_failed"}
                                    continue
                                rank = rank_public_meld_sift(bank, normalized,
                                    source_session=face["source_session"], source_sha256=face["source_sha256"],
                                    minimum_other_match_groups=1, include_class_scores=True)
                                scorable = face["reviewed_candidate_tile"] in rank["class_scores"]
                                modes[mode] = {"scorable": scorable, "top1": rank["top1_tile"],
                                    "correct": rank["top1_tile"] == face["reviewed_candidate_tile"] if scorable else None,
                                    "reason": rank["reason"]}
                            rows.append({"group_id": group["group_id"], "frame": frame, "face_index": i,
                                "reviewed_candidate_tile": face["reviewed_candidate_tile"], "modes": modes})
            finally:
                cap.release()
    summary = {}
    for mode in ("pinned_direct", "raw_equal_thirds", "raw_equal_thirds_two_pixel_seam_context"):
        summary[mode] = {}
        for group in (g["group_id"] for source in spec["sources"] for g in source["groups"]):
            selected = [r for r in rows if r["group_id"] == group]
            summary[mode][group] = {"face_rows": len(selected),
                "scorable": sum(r["modes"][mode]["scorable"] for r in selected),
                "correct_when_scorable": sum(r["modes"][mode]["correct"] is True for r in selected),
                "group_frame_correct_when_scorable": sum(
                    all(r["modes"][mode]["correct"] is True for r in selected if r["frame"] == frame)
                    for frame in sorted({r["frame"] for r in selected})
                    if all(r["modes"][mode]["scorable"] for r in selected if r["frame"] == frame))}
    return {"schema_version": "existing_group_seam_context_dev_v0_1", "rows": rows,
        "summary": summary, "private_template_load": loaded,
        "intake_ledger_sha256": hashlib.sha256(pin_path.read_bytes()).hexdigest(),
        "opencv_version": cv2.__version__, "original_query_match_count": 1,
        "two_pixel_margin_chosen_after_hand8_inspection": True,
        "independent_holdout": False, "missing_reference_classes_are_not_counted_correct": True,
        "runtime_integration": False, "safe_for_runtime": False,
        "safe_for_hint": False, "safe_for_executor": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video-dir", required=True)
    parser.add_argument("--intake-zip", required=True)
    parser.add_argument("--private-template-zip", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        parser.error("output exists; preserve earlier evidence")
    result = evaluate(video_dir=args.video_dir, intake_zip=args.intake_zip,
        private_template_zip=args.private_template_zip)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["summary"]))


if __name__ == "__main__":
    main()
