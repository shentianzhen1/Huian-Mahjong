"""Source-pinned geometry-only neighbor experiment on all 105 frozen crops."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile


def load_frozen_groups(root, native_zip, private_zip, query_zips, *, include_public_s789=False):
    from PIL import Image
    from workspace.vision import public_meld_identity_sift as sift
    from workspace.vision import public_meld_private_sift_loader as private
    from workspace.vision.public_identity_labels import load_public_identity_manifest
    from workspace.vision.public_meld_private_recovery_result import load_private_recovery_results, RecoveredPrivateTemplate
    root = Path(root).resolve()
    groups = []
    inputs = {}
    def load_pin(relative):
        path = root / relative
        inputs[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        return json.loads(path.read_text())
    def read(archive, name, digest):
        raw = archive.read(name)
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("crop hash changed: " + name)
        return Image.open(io.BytesIO(raw)).convert("RGB")
    if include_public_s789:
        from workspace.vision.public_identity_labels import (
            approved_labels, load_public_identity_manifest, pixel_bbox,
            verify_repository_files,
        )
        from workspace.vision.public_identity_shadow_v0_2 import load_development_sources
        manifest_path = root / "references/vision/2026-09-22/public_identity_labels_v0_1.json"
        manifest = load_public_identity_manifest(manifest_path)
        issues = verify_repository_files(manifest, root)
        if issues:
            raise ValueError("public S789 source image verification failed: " + ",".join(issues))
        registry_path = root / "references/vision/2026-09-24/public_identity_source_groups.development.json"
        sources = load_development_sources(registry_path)
        labels = {label.label_id: label for label in approved_labels(manifest)
                  if label.label_id in {"public_meld_s7", "public_meld_s8", "public_meld_s9"}}
        if set(labels) != {"public_meld_s7", "public_meld_s8", "public_meld_s9"}:
            raise ValueError("frozen public S789 control group is incomplete")
        if len({(label.source_sha256, label.frame_index, label.image_path)
                for label in labels.values()}) != 1:
            raise ValueError("public S789 labels are not from the same source frame")
        inputs["references/vision/2026-09-22/public_identity_labels_v0_1.json"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        inputs["references/vision/2026-09-24/public_identity_source_groups.development.json"] = hashlib.sha256(registry_path.read_bytes()).hexdigest()
        label = labels["public_meld_s7"]
        source = sources.get(label.source_session)
        if source is None or source.source_sha256 != label.source_sha256:
            raise ValueError("public S789 source lineage is not registered")
        with Image.open(root / label.image_path) as frame:
            frame = frame.convert("RGB")
            row = []
            for tile in ("S7", "S8", "S9"):
                label = labels[f"public_meld_{tile.lower()}"]
                x, y, w, h = pixel_bbox(label, frame.size)
                crop = frame.crop((x, y, x+w, y+h))
                row.append((dict(query_id=label.label_id, packet="public_reference_controls",
                    expected_visual_tile=tile, source_sha256=label.source_sha256,
                    source_frame_pin=label.frame_index, source_session=label.source_session,
                    original_match_group=source.match_group,
                    crop_sha256=hashlib.sha256(crop.tobytes()).hexdigest(), bounds=[x,y,x+w,y+h],
                    image_sha256=label.image_sha256, label_id=label.label_id), crop))
            groups.append(row)
    native_path = "references/vision/2026-10-04/new_match_native_reference_candidate_pin_v0_1.json"
    with ZipFile(native_zip) as archive:
        pin = load_pin(native_path)
        if json.loads(archive.read("reference_pin.json")) != pin:
            raise ValueError("native reference pin mismatch")
        grouped = defaultdict(list)
        for f in pin["reference_faces"]:
            # Source frame and match lineage, never tile label, select peers.
            key = (f["source_sha256"], f["native_frame_png_sha256"], f["reference_group"])
            grouped[key].append((dict(query_id=f'native_reverse_{f["reference_group"]}_{f["face_index"]}',
                packet="new_native", expected_visual_tile=f["provisional_visual_tile"],
                source_sha256=f["source_sha256"], source_frame_pin=f["native_frame_png_sha256"],
                original_match_group=f["original_match_group"], crop_sha256=f["crop_png_sha256"],
                bounds=f["native_xyxy"]), read(archive, f["crop_file"], f["crop_png_sha256"])))
        groups.extend(grouped.values())
    recovery_path = "references/vision/2026-10-02/public_meld_private_recovery_result_v0_3.json"
    load_pin(recovery_path)
    manifest = load_public_identity_manifest(root / "references/vision/2026-09-22/public_identity_labels_v0_1.json")
    bank = sift.build_public_meld_sift_bank(manifest, root,
        root / "references/vision/2026-09-24/public_identity_source_groups.development.json")
    # Keep the original strict manifest/source/frame/crop verification intact.
    private.augment_public_meld_sift_bank_from_private_zip(bank, private_zip_path=private_zip,
        recovery_result_path=root / recovery_path, repository_root=root)
    records = [r for r in load_private_recovery_results(root / recovery_path).values() if isinstance(r, RecoveredPrivateTemplate)]
    with ZipFile(private_zip) as archive:
        payload = json.loads(archive.read(records[0].private_label_manifest_name))
        for record in records:
            group = private._matching_private_group(tuple(payload["groups"]), record)
            row = []
            for index, face in enumerate(group["faces"]):
                x, y, w, h = face["bbox"]
                row.append((dict(query_id=f"{record.recovery_id}_{index}", packet="private_reviewed_controls",
                    expected_visual_tile=record.tile_ids[index], source_sha256=record.source_sha256,
                    source_frame_pin=record.frame_index, original_match_group=record.match_group,
                    crop_sha256=record.crop_sha256[index], bounds=[x, y, x+w, y+h]),
                    read(archive, "approved_faces/"+face["crop_file"], record.crop_sha256[index])))
            groups.append(row)
    for path in query_zips:
        with ZipFile(path) as archive:
            name = "hand8_s789_intake_v0_1.json" if "s789" in Path(path).name else "existing_video_meld_face_intake_v0_1.json"
            pin = load_pin("references/vision/2026-10-03/"+name)
            if json.loads(archive.read("intake.json")) != pin:
                raise ValueError("old query pin mismatch")
            grouped = defaultdict(list)
            for f in pin["faces"]:
                x, y, w, h = f["bbox"]
                key = (f["source_sha256"], f["frame_index"], f["group_id"])
                grouped[key].append((dict(query_id=f'{f["group_id"]}_{f["frame_index"]}_{f["face_index"]}',
                    packet="old_manual_crops", expected_visual_tile=f["reviewed_candidate_tile"],
                    source_sha256=f["source_sha256"], source_frame_pin=f["frame_index"],
                    original_match_group=pin["spec"]["conservative_original_match_group"],
                    crop_sha256=f["crop_sha256"], bounds=[x,y,x+w,y+h]),
                    read(archive, f["crop_file"], f["crop_sha256"])))
            groups.extend(grouped.values())
    return groups, inputs


def evaluate(root, native_zip, private_zip, query_zips, review_directory=None):
    from workspace.vision.public_meld_bracketed_front_band_probe import prepare_bracketed_front_band
    from workspace.vision.public_meld_front_band_probe import prepare_front_band
    groups, inputs = load_frozen_groups(root, native_zip, private_zip, query_zips)
    if review_directory:
        review_directory = Path(review_directory)
        review_directory.mkdir(parents=True, exist_ok=True)
    rows = []
    for group in groups:
        if len(group) != 3:
            raise ValueError("frozen three-face row incomplete")
        if len({(m["source_sha256"], m["source_frame_pin"], m["original_match_group"]) for m, _ in group}) != 1:
            raise ValueError("neighbor source/frame/match mismatch")
        for index, (meta, image) in enumerate(group):
            direct, direct_audit = prepare_front_band(image, merge_overlaps=True)
            other = [(im, m["bounds"]) for j, (m, im) in enumerate(group) if j != index]
            prepared, audit = prepare_bracketed_front_band(image, meta["bounds"], other)
            if direct is not None and (prepared is None or direct.tobytes() != prepared.tobytes() or direct.size != prepared.size):
                raise RuntimeError("direct geometry candidate changed")
            row = dict(**meta, direct_status="CANDIDATE" if direct is not None else "UNKNOWN",
                peer_status="CANDIDATE" if prepared is not None else "UNKNOWN", peer_preparation=audit,
                same_frame_neighbor_query_ids=[m["query_id"] for j, (m, _) in enumerate(group) if j != index])
            if prepared is not None:
                raw = io.BytesIO(); prepared.save(raw, format="PNG")
                row.update(prepared_size=list(prepared.size), prepared_png_sha256=hashlib.sha256(raw.getvalue()).hexdigest())
            if review_directory and direct is None:
                image.save(review_directory / (meta["query_id"]+"_source.png"))
                if prepared is not None:
                    prepared.save(review_directory / (meta["query_id"]+"_peer.png"))
            rows.append(row)
    if len({r["query_id"] for r in rows}) != len(rows):
        raise ValueError("duplicate query ID")
    summary = {}
    for packet in sorted({r["packet"] for r in rows}):
        subset = [r for r in rows if r["packet"] == packet]
        summary[packet] = dict(faces=len(subset), direct_candidates=sum(r["direct_status"]=="CANDIDATE" for r in subset),
            peer_candidates=sum(r["peer_status"]=="CANDIDATE" for r in subset),
            recovered_ids=[r["query_id"] for r in subset if r["direct_status"]=="UNKNOWN" and r["peer_status"]=="CANDIDATE"],
            unknown_reasons=dict(Counter(r["peer_preparation"]["reason"] for r in subset if r["peer_status"]=="UNKNOWN")))
    return dict(schema_version="bracketed_front_band_geometry_dev_v0_1", rows=rows, summary=summary,
        input_pin_sha256=inputs, query_count=len(rows), row_groups=len(groups),
        crop_hashes_and_manifests_verified=True, private_loader_verification_contract_changed=False,
        original_video_hash_audit="inherited frozen intake; video bytes not reread by this probe",
        direct_candidates_byte_preserved=True, labels_used_for_geometry=False,
        manual_split_rois=True, automatic_group_detection_or_splitting_verified=False,
        geometry_only=True, identity_scores_computed=False, exact_face_plane_ground_truth_available=False,
        candidate_count_is_not_accuracy=True, previously_inspected=True, blind_holdout=False,
        parameters_selected_after_previous_failure_review=True, formal_promotion_evidence=False,
        peer_pixels_are_independent_sources=False, raw_feature_fallback=False,
        runtime_identity_threshold=0.82, runtime_integration=False,
        safe_for_runtime=False, safe_for_hint=False, safe_for_executor=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--native-reference-zip", required=True)
    parser.add_argument("--private-template-zip", required=True)
    parser.add_argument("--query-zip", action="append", required=True)
    parser.add_argument("--review-directory")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = evaluate(args.repository_root, args.native_reference_zip, args.private_template_zip, args.query_zip, args.review_directory)
    Path(args.output).write_text(json.dumps(result, separators=(",", ":"))+"\n")
    print(json.dumps(result["summary"]))


if __name__ == "__main__":
    main()
