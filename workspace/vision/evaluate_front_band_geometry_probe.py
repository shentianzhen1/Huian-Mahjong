"""Hash-locked development geometry audit; does not score tile identities."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile


def evaluate(root, native_zip, query_zips, review_directory=None):
    from PIL import Image
    from workspace.vision.evaluate_sift_symmetric_geometry_probe import normalize_single_face
    from workspace.vision.public_meld_front_band_probe import front_band_bbox
    root = Path(root).resolve()
    queries = []
    def read(archive, filename, digest):
        raw = archive.read(filename)
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("crop hash changed")
        return Image.open(io.BytesIO(raw)).convert("RGB")
    with ZipFile(native_zip) as archive:
        pin = json.loads(archive.read("reference_pin.json"))
        if pin != json.loads((root / "references/vision/2026-10-04/new_match_native_reference_candidate_pin_v0_1.json").read_text()):
            raise ValueError("native reference pin mismatch")
        for face in pin["reference_faces"]:
            queries.append((dict(query_id=f'native_{face["reference_group"]}_{face["face_index"]}',
                packet="new_native", expected_visual_tile=face["provisional_visual_tile"],
                crop_sha256=face["crop_png_sha256"], original_match_group=face["original_match_group"],
                source_sha256=face["source_sha256"]), read(archive, face["crop_file"], face["crop_png_sha256"])))
    for path in query_zips:
        with ZipFile(path) as archive:
            payload = json.loads(archive.read("intake.json"))
            name = "hand8_s789_intake_v0_1.json" if "s789" in Path(path).name else "existing_video_meld_face_intake_v0_1.json"
            if payload != json.loads((root / "references/vision/2026-10-03" / name).read_text()):
                raise ValueError("old query pin mismatch")
            for face in payload["faces"]:
                queries.append((dict(query_id=f'{face["group_id"]}_{face["frame_index"]}_{face["face_index"]}',
                    packet="old_manual_crops", group_id=face["group_id"], frame_index=face["frame_index"],
                    expected_visual_tile=face["reviewed_candidate_tile"], crop_sha256=face["crop_sha256"],
                    original_match_group=payload["spec"]["conservative_original_match_group"],
                    source_sha256=face["source_sha256"]), read(archive, face["crop_file"], face["crop_sha256"])))
    rows = []
    if review_directory:
        review_directory = Path(review_directory)
        review_directory.mkdir(parents=True, exist_ok=True)
    for meta, image in queries:
        normalized, normalization_audit = normalize_single_face(image)
        if normalized is None:
            rows.append(dict(**meta, status="UNKNOWN", reason="normalization_abstained"))
            continue
        box, audit = front_band_bbox(normalized)
        row = dict(**meta, normalized_size=list(normalized.size), geometry_audit=audit,
                   status="CANDIDATE" if box else "UNKNOWN")
        if box:
            crop = normalized.crop(box)
            buffer = io.BytesIO(); crop.save(buffer, format="PNG")
            row.update(front_band_png_sha256=hashlib.sha256(buffer.getvalue()).hexdigest(),
                       front_band_bbox=list(box), front_band_size=list(crop.size))
            if review_directory:
                normalized.save(review_directory / (meta["query_id"] + "_normalized.png"))
                crop.save(review_directory / (meta["query_id"] + "_front.png"))
        elif review_directory:
            normalized.save(review_directory / (meta["query_id"] + "_normalized.png"))
        rows.append(row)
    summary = {packet: dict(Counter(r["status"] for r in rows if r["packet"] == packet)) for packet in sorted({r["packet"] for r in rows})}
    return dict(schema_version="front_band_geometry_probe_dev_v0_1", rows=rows, summary=summary,
        query_count=len(rows), distinct_original_matches=len({r["original_match_group"] for r in rows}),
        crop_hashes_and_manifests_verified=True, original_video_hash_audit="inherited prior intake",
        parameters_frozen_before_this_batch=True, geometry_only=True, identity_scores_computed=False,
        exact_pixel_front_plane_ground_truth_available=False, candidate_count_is_not_accuracy=True,
        labels_not_used_by_geometry=True, previously_inspected=True, blind_holdout=False,
        full_face_plane_rectification=False, formal_promotion_evidence=False,
        runtime_identity_threshold=0.82, runtime_integration=False,
        safe_for_runtime=False, safe_for_hint=False, safe_for_executor=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--native-reference-zip", required=True)
    parser.add_argument("--query-zip", action="append", required=True)
    parser.add_argument("--review-directory")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = evaluate(args.repository_root, args.native_reference_zip, args.query_zip, args.review_directory)
    Path(args.output).write_text(json.dumps(report, separators=(",", ":"))+"\n")
    print(json.dumps(report["summary"]))


if __name__ == "__main__":
    main()
