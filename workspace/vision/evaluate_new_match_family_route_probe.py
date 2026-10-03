"""Offline family-routing falsification; SIFT winners are not calibrated gates.

Frozen whole-face SIFT proposes a family before the existing Wan digit feature.
Expected labels are used only for reporting, never for routing. No Runtime caller.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile


def evaluate(*, root: Path, native_zip: Path, private_zip: Path,
             query_zips: list[Path]) -> dict:
    from PIL import Image
    from workspace.vision import public_meld_identity_sift as sift
    from workspace.vision import public_meld_private_sift_loader as private
    from workspace.vision.public_identity_labels import load_public_identity_manifest, approved_labels, pixel_bbox
    from workspace.vision.public_identity_shadow_v0_2 import SourceGroup
    from workspace.vision.public_meld_private_recovery_result import load_private_recovery_results, RecoveredPrivateTemplate
    from workspace.vision.evaluate_sift_symmetric_geometry_probe import normalize_single_face

    root = root.resolve()
    original = sift._sift_descriptors
    def whole(image):
        normalized, _ = normalize_single_face(image)
        return None if normalized is None else original(normalized)
    def digit(image):
        normalized, _ = normalize_single_face(image)
        if normalized is None:
            return None
        upper = normalized.crop((0, 0, normalized.width, max(1, normalized.height // 2)))
        return original(upper.resize((72, 96), Image.Resampling.LANCZOS))
    def read_face(archive, name, digest):
        raw = archive.read(name)
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("crop pin mismatch: " + name)
        with Image.open(io.BytesIO(raw)) as image:
            return image.convert("RGB")
    alias = {"reviewed_match_2026_09_26_first_hand", "reviewed_match_2026_09_26_eight_hand"}
    canonical = "reviewed_match_2026_09_26_eight_hand"
    manifest = load_public_identity_manifest(root / "references/vision/2026-09-22/public_identity_labels_v0_1.json")
    recovery = root / "references/vision/2026-10-02/public_meld_private_recovery_result_v0_3.json"
    registry = root / "references/vision/2026-09-24/public_identity_source_groups.development.json"
    banks = {}
    for name, transform in (("whole", whole), ("digit", digit)):
        with patch.object(sift, "_sift_descriptors", transform), patch.object(private, "_sift_descriptors", transform):
            bank = sift.build_public_meld_sift_bank(manifest, root, registry)
            bank, _ = private.augment_public_meld_sift_bank_from_private_zip(
                bank, private_zip_path=private_zip, recovery_result_path=recovery, repository_root=root)
        sources = {key: replace(value, match_group=canonical if value.match_group in alias else value.match_group)
                   for key, value in bank.sources.items()}
        templates = [replace(t, match_group=canonical if t.match_group in alias else t.match_group)
                     for t in bank.templates if name == "whole" or t.tile_id.startswith("M")]
        with ZipFile(native_zip) as archive:
            pin = json.loads(archive.read("reference_pin.json"))
            pinned = json.loads((root / "references/vision/2026-10-04/new_match_native_reference_candidate_pin_v0_1.json").read_text())
            if pin != pinned:
                raise ValueError("native reference manifest mismatch")
            for face in pin["reference_faces"]:
                image = read_face(archive, face["crop_file"], face["crop_png_sha256"])
                session, digest, group = face["source_session"], face["source_sha256"], face["original_match_group"]
                sources[session] = SourceGroup(session, digest, group)
                tile = face["provisional_visual_tile"]
                if name == "digit" and not tile.startswith("M"):
                    continue
                descriptors = transform(image)
                if descriptors is None:
                    raise ValueError("reference lacks descriptors")
                templates.append(sift.PublicMeldSiftTemplate(tile, session, digest, group, descriptors))
        banks[name] = sift.PublicMeldSiftBank(sources, tuple(templates))

    queries = []
    def add(meta, image):
        queries.append((meta, image))
    for label in approved_labels(manifest):
        if label.region != "public_meld":
            continue
        with Image.open(root / label.image_path) as image:
            image = image.convert("RGB")
            x, y, w, h = pixel_bbox(label, image.size)
            add(dict(query_id=label.label_id, set="public_controls", expected=label.tile_id,
                     session=label.source_session, sha256=label.source_sha256), image.crop((x, y, x+w, y+h)))
    recovered = [r for r in load_private_recovery_results(recovery).values() if isinstance(r, RecoveredPrivateTemplate)]
    with ZipFile(private_zip) as archive:
        groups = tuple(json.loads(archive.read(recovered[0].private_label_manifest_name))["groups"])
        for record in recovered:
            group = private._matching_private_group(groups, record)
            for index, face in enumerate(group["faces"]):
                add(dict(query_id=f"{record.recovery_id}_{index}", set="private_reviewed_controls",
                         expected=record.tile_ids[index], session="private_recovered_"+record.recovery_id,
                         sha256=record.source_sha256, crop_sha256=record.crop_sha256[index]),
                    read_face(archive, "approved_faces/"+face["crop_file"], record.crop_sha256[index]))
    for path in query_zips:
        with ZipFile(path) as archive:
            payload = json.loads(archive.read("intake.json"))
            pin_name = "hand8_s789_intake_v0_1.json" if "s789" in path.name else "existing_video_meld_face_intake_v0_1.json"
            if payload != json.loads((root / "references/vision/2026-10-03" / pin_name).read_text()):
                raise ValueError("old query manifest mismatch")
            for source in payload["spec"]["sources"]:
                for bank in banks.values():
                    bank.sources[source["source_session"]] = SourceGroup(source["source_session"], source["source_sha256"], payload["spec"]["conservative_original_match_group"])
            for face in payload["faces"]:
                add(dict(query_id=f'{face["group_id"]}_{face["frame_index"]}_{face["face_index"]}',
                         set="old_manual_crops", expected=face["reviewed_candidate_tile"],
                         session=face["source_session"], sha256=face["source_sha256"], crop_sha256=face["crop_sha256"]),
                    read_face(archive, face["crop_file"], face["crop_sha256"]))

    # A draw-domain M8 is only a stress query. It is never a public-meld template.
    label = next(json.loads(line) for line in (root / "dataset/tiles_runtime_v0_2/labels.jsonl").read_text().splitlines()
                 if json.loads(line).get("id") == "tile_aaa921b08dbfec79")
    path = root / "dataset/tiles_runtime_v0_2" / label["image"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != label["asset_sha256"]:
        raise ValueError("M8 stress crop hash changed")
    known = {s.match_group for s in banks["whole"].sources.values() if s.source_sha256 == label["sha256"]}
    if len(known) > 1:
        raise ValueError("ambiguous M8 source group")
    for bank in banks.values():
        bank.sources[label["source_session"]] = SourceGroup(label["source_session"], label["sha256"], next(iter(known), "unresolved_M8_stress_original"))
    with Image.open(path) as image:
        add(dict(query_id=label["id"], set="M8_draw_domain_stress_only", expected="M8",
                 session=label["source_session"], sha256=label["sha256"], crop_sha256=label["asset_sha256"],
                 original_match_lineage_resolved=bool(known)), image.convert("RGB"))

    rows = []
    for meta, image in queries:
        modes = {}
        for minimum in (1, 2):
            with patch.object(sift, "_sift_descriptors", whole):
                rank = sift.rank_public_meld_sift(banks["whole"], image, source_session=meta["session"], source_sha256=meta["sha256"], minimum_other_match_groups=minimum, include_class_scores=True)
            top = rank["top1_tile"]
            family = top[0] if top and top[0] in "MPS" else ("HONOR" if top else None)
            expected_family = meta["expected"][0] if meta["expected"][0] in "MPS" else "HONOR"
            routed = family == "M"
            digit_rank = None
            if routed:
                with patch.object(sift, "_sift_descriptors", digit):
                    digit_rank = sift.rank_public_meld_sift(banks["digit"], image, source_session=meta["session"], source_sha256=meta["sha256"], minimum_other_match_groups=minimum, include_class_scores=True)
            modes[str(minimum)] = dict(family_ranking=rank, observed_family=family,
                family_correct=family == expected_family if family else None,
                expected_identity_scorable=meta["expected"] in rank["class_scores"],
                routed_to_wan_digit=routed, false_wan_route=routed and expected_family != "M",
                digit_ranking=digit_rank,
                routed_expected_identity_scorable=meta["expected"] in digit_rank["class_scores"] if digit_rank else None,
                routed_identity_correct=digit_rank["top1_tile"] == meta["expected"] if digit_rank else None)
        rows.append(dict(**meta, modes=modes))
    summary = {}
    for minimum in ("1", "2"):
        summary[minimum] = {}
        for subset in sorted({r["set"] for r in rows}):
            selected = [r for r in rows if r["set"] == subset]
            summary[minimum][subset] = dict(faces=len(selected),
                family_correct=sum(r["modes"][minimum]["family_correct"] is True for r in selected),
                no_ranking=sum(r["modes"][minimum]["observed_family"] is None for r in selected),
                false_wan_routes=sum(r["modes"][minimum]["false_wan_route"] for r in selected),
                expected_wan_faces=sum(r["expected"].startswith("M") for r in selected),
                wan_routes=sum(r["modes"][minimum]["routed_to_wan_digit"] for r in selected),
                expected_identity_unscorable=sum(not r["modes"][minimum]["expected_identity_scorable"] for r in selected),
                routed_expected_identity_unscorable=sum(r["modes"][minimum]["routed_expected_identity_scorable"] is False for r in selected),
                routed_correct_identities=sum(r["modes"][minimum]["routed_identity_correct"] is True for r in selected))
    return dict(schema_version="new_match_family_route_falsification_dev_v0_1", summary=summary, rows=rows,
        whole_bank_classes=sorted({t.tile_id for t in banks["whole"].templates}),
        routing_rule="whole-face source-disjoint SIFT winner's family; no label-selected family; absent winner abstains",
        score_is_calibrated_confidence=False, confidence_threshold_selected=False,
        crop_ratio_search_performed=False, upper_crop_fraction=0.5, upper_feature_size=[72,96],
        same_original_match_aliases_collapsed=sorted(alias), crop_hashes_and_source_registries_verified=True,
        native_video_hash_audit="inherited frozen reference intake; this evaluator verifies crop bytes and pin equality",
        reference_selection="previous frozen native 15-face pin; no new samples chosen by score",
        M8_reference_added=False, M8_draw_domain_is_public_meld_evidence=False,
        decision="reject winner-family routing as an automatic identity gate",
        rejection_reasons=["non-Wan crops enter the Wan head", "unsupported M8 stress query ranks as M9", "SIFT winners provide no calibrated abstention"],
        oracle_family_used_for_routing=False, previously_inspected=True, blind_holdout=False,
        default_bank_modified=False, runtime_identity_threshold=0.82, runtime_integration=False,
        formal_promotion_evidence=False, safe_for_runtime=False, safe_for_hint=False, safe_for_executor=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--native-reference-zip", type=Path, required=True)
    parser.add_argument("--private-template-zip", type=Path, required=True)
    parser.add_argument("--query-zip", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(root=args.repository_root, native_zip=args.native_reference_zip,
                      private_zip=args.private_template_zip, query_zips=args.query_zip)
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report["summary"]))


if __name__ == "__main__":
    main()
