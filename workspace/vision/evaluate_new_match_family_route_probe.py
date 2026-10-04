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


def lower_family_consensus(whole_rank: dict, lower_rank: dict) -> str:
    """Return an offline hypothesis; disagreement/missing competition abstains.

    These two features share pixels and are NOT independent corroboration.
    No score or margin threshold is learned here, and no identity is accepted.
    """
    tile = whole_rank.get("top1_tile")
    binary = lower_rank.get("top1_tile")
    if (not tile or binary not in {"WAN", "NON_WAN"}
            or set(lower_rank.get("class_scores", {})) != {"WAN", "NON_WAN"}
            or (whole_rank.get("margin") or 0) <= 0
            or (lower_rank.get("margin") or 0) <= 0):
        return "UNKNOWN"
    whole_is_wan = tile.startswith("M")
    if whole_is_wan != (binary == "WAN"):
        return "UNKNOWN"
    return "WAN" if whole_is_wan else "NON_WAN"


def wan_other_original_support(bank, session: str, source_sha256: str) -> dict[str, int]:
    """Count distinct original matches, excluding query match and exact SHA.

    The caller must first collapse original-match aliases in the bank.
    """
    source = bank.sources[session]
    if source.source_sha256 != source_sha256:
        raise ValueError("query source SHA mismatch")
    return {f"M{i}": len({t.match_group for t in bank.templates
        if t.tile_id == f"M{i}" and t.match_group != source.match_group
        and t.source_sha256 != source_sha256}) for i in range(1, 10)}


def evaluate(*, root: Path, native_zip: Path, private_zip: Path,
             query_zips: list[Path], lower_consensus: bool = False,
             front_band: bool = False, reverse_old_m9: bool = False,
             merge_front_overlaps: bool = False) -> dict:
    from PIL import Image
    from workspace.vision import public_meld_identity_sift as sift
    from workspace.vision import public_meld_private_sift_loader as private
    from workspace.vision.public_identity_labels import load_public_identity_manifest, approved_labels, pixel_bbox
    from workspace.vision.public_identity_shadow_v0_2 import SourceGroup
    from workspace.vision.public_meld_private_recovery_result import load_private_recovery_results, RecoveredPrivateTemplate
    from workspace.vision.evaluate_sift_symmetric_geometry_probe import normalize_single_face
    from workspace.vision.public_meld_front_band_probe import prepare_front_band

    root = root.resolve()
    if front_band and not lower_consensus:
        raise ValueError("front-band comparison requires lower-family consensus")
    if reverse_old_m9 and not lower_consensus:
        raise ValueError("reverse-reference comparison requires lower-family consensus")
    if merge_front_overlaps and not front_band:
        raise ValueError("component merging requires front-band mode")
    original = sift._sift_descriptors
    def prepare(image):
        return prepare_front_band(image, merge_overlaps=merge_front_overlaps) if front_band else normalize_single_face(image)
    def whole(image):
        normalized, _ = prepare(image)
        return None if normalized is None else original(normalized)
    def digit(image):
        normalized, _ = prepare(image)
        if normalized is None:
            return None
        upper = normalized.crop((0, 0, normalized.width, max(1, normalized.height // 2)))
        return original(upper.resize((72, 96), Image.Resampling.LANCZOS))
    def lower(image):
        normalized, _ = prepare(image)
        if normalized is None:
            return None
        body = normalized.crop((0, normalized.height // 2, normalized.width, normalized.height))
        return original(body.resize((72, 96), Image.Resampling.LANCZOS))
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
    native_reference_abstentions = []
    private_feature_abstentions = []
    raw_private_templates = []
    verified_private_bank = None
    if front_band:
        # Preserve the strict loader's original verification contract. A new
        # geometry abstention is an experiment outcome, never a weaker ZIP pin.
        verified_private_bank = sift.build_public_meld_sift_bank(manifest, root, registry)
        verified_private_bank, _ = private.augment_public_meld_sift_bank_from_private_zip(
            verified_private_bank, private_zip_path=private_zip,
            recovery_result_path=recovery, repository_root=root)
        recovered_for_features = [r for r in load_private_recovery_results(recovery).values() if isinstance(r, RecoveredPrivateTemplate)]
        with ZipFile(private_zip) as archive:
            groups = tuple(json.loads(archive.read(recovered_for_features[0].private_label_manifest_name))["groups"])
            for record in recovered_for_features:
                group = private._matching_private_group(groups, record)
                for index, face in enumerate(group["faces"]):
                    raw_private_templates.append((record, index,
                        read_face(archive, "approved_faces/"+face["crop_file"], record.crop_sha256[index])))
    transforms = [("whole", whole), ("digit", digit)]
    if lower_consensus:
        transforms.append(("lower", lower))
    for name, transform in transforms:
        with patch.object(sift, "_sift_descriptors", transform), patch.object(private, "_sift_descriptors", transform):
            bank = sift.build_public_meld_sift_bank(manifest, root, registry)
            if not front_band:
                bank, _ = private.augment_public_meld_sift_bank_from_private_zip(
                    bank, private_zip_path=private_zip, recovery_result_path=recovery, repository_root=root)
        if front_band:
            transformed_private = []
            for record, index, image in raw_private_templates:
                tile = record.tile_ids[index]
                if name == "digit" and not tile.startswith("M"):
                    continue
                descriptors = transform(image)
                if descriptors is None:
                    private_feature_abstentions.append(dict(feature=name, recovery_id=record.recovery_id, face_index=index, expected=tile))
                    continue
                transformed_private.append(sift.PublicMeldSiftTemplate(tile, "private_recovered_"+record.recovery_id,
                    record.source_sha256, record.match_group, descriptors))
            bank = sift.PublicMeldSiftBank(verified_private_bank.sources, bank.templates+tuple(transformed_private))
        sources = {key: replace(value, match_group=canonical if value.match_group in alias else value.match_group)
                   for key, value in bank.sources.items()}
        templates = [replace(t, match_group=canonical if t.match_group in alias else t.match_group)
                     for t in bank.templates if name != "digit" or t.tile_id.startswith("M")]
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
                    if front_band:
                        native_reference_abstentions.append(dict(feature=name, crop_file=face["crop_file"], expected=tile))
                        continue
                    raise ValueError("reference lacks descriptors")
                templates.append(sift.PublicMeldSiftTemplate(tile, session, digest, group, descriptors))
        banks[name] = sift.PublicMeldSiftBank(sources, tuple(templates))
        if name == "lower":
            banks[name] = sift.PublicMeldSiftBank(sources, tuple(
                replace(t, tile_id="WAN" if t.tile_id.startswith("M") else "NON_WAN") for t in templates))

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

    if lower_consensus:
        # Reverse direction: reuse ALL frozen faces as queries, excluding their
        # entire original match from both banks. No new reference selection.
        with ZipFile(native_zip) as archive:
            for face in pin["reference_faces"]:
                add(dict(query_id=f'native_reverse_{face["reference_group"]}_{face["face_index"]}',
                         set="new_native_reverse_queries", expected=face["provisional_visual_tile"],
                         session=face["source_session"], sha256=face["source_sha256"],
                         crop_sha256=face["crop_png_sha256"]),
                    read_face(archive, face["crop_file"], face["crop_png_sha256"]))

    reverse_reference_rows = []
    if reverse_old_m9:
        # All three faces of already frozen frame 4794; no score-driven choice.
        selected = [(meta, image) for meta, image in queries
                    if meta["query_id"].startswith("hand8_wan9_4794_")]
        if len(selected) != 3 or any(meta["expected"] != "M9" for meta, _ in selected):
            raise ValueError("frozen old M9 reference group missing")
        for name, transform in transforms:
            bank = banks[name]
            additions = []
            for meta, image in selected:
                descriptors = transform(image)
                eligible = descriptors is not None
                reverse_reference_rows.append(dict(feature=name, query_id=meta["query_id"],
                    crop_sha256=meta["crop_sha256"], feature_available=eligible))
                if eligible:
                    source = bank.sources[meta["session"]]
                    additions.append(sift.PublicMeldSiftTemplate("WAN" if name == "lower" else "M9",
                        meta["session"], meta["sha256"], source.match_group, descriptors))
            banks[name] = sift.PublicMeldSiftBank(bank.sources, bank.templates+tuple(additions))

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
            lower_rank = None
            consensus = None
            if lower_consensus:
                with patch.object(sift, "_sift_descriptors", lower):
                    lower_rank = sift.rank_public_meld_sift(banks["lower"], image, source_session=meta["session"], source_sha256=meta["sha256"], minimum_other_match_groups=minimum, include_class_scores=True)
                consensus = lower_family_consensus(rank, lower_rank)
            routed = consensus == "WAN" if lower_consensus else family == "M"
            digit_rank = None
            if routed:
                with patch.object(sift, "_sift_descriptors", digit):
                    digit_rank = sift.rank_public_meld_sift(banks["digit"], image, source_session=meta["session"], source_sha256=meta["sha256"], minimum_other_match_groups=minimum, include_class_scores=True)
            modes[str(minimum)] = dict(family_ranking=rank, observed_family=family,
                lower_binary_ranking=lower_rank, family_consensus=consensus,
                consensus_correct=(consensus == ("WAN" if expected_family == "M" else "NON_WAN")) if consensus not in (None, "UNKNOWN") else None,
                family_correct=family == expected_family if family else None,
                expected_identity_scorable=meta["expected"] in rank["class_scores"],
                routed_to_wan_digit=routed, false_wan_route=routed and expected_family != "M",
                digit_ranking=digit_rank,
                routed_expected_identity_scorable=meta["expected"] in digit_rank["class_scores"] if digit_rank else None,
                routed_identity_correct=digit_rank["top1_tile"] == meta["expected"] if digit_rank else None)
            if lower_consensus:
                support = wan_other_original_support(banks["digit"], meta["session"], meta["sha256"])
                modes[str(minimum)]["wan_class_other_original_support"] = support
                modes[str(minimum)]["wan_alphabet_support_complete"] = all(n >= minimum for n in support.values())
                modes[str(minimum)]["qualified_identity"] = None
                modes[str(minimum)]["identity_abstention_reason"] = "unqualified_development_scores" if all(n >= minimum for n in support.values()) else "incomplete_source_disjoint_Wan_alphabet"
        preparation = prepare(image)[1] if front_band else None
        rows.append(dict(**meta, modes=modes, feature_preparation=preparation))
    summary = {}
    for minimum in ("1", "2"):
        summary[minimum] = {}
        for subset in sorted({r["set"] for r in rows}):
            selected = [r for r in rows if r["set"] == subset]
            summary[minimum][subset] = dict(faces=len(selected),
                family_correct=sum(r["modes"][minimum]["family_correct"] is True for r in selected),
                no_ranking=sum(r["modes"][minimum]["observed_family"] is None for r in selected),
                consensus_unknown=sum(r["modes"][minimum]["family_consensus"] == "UNKNOWN" for r in selected),
                consensus_correct=sum(r["modes"][minimum]["consensus_correct"] is True for r in selected),
                consensus_incorrect=sum(r["modes"][minimum]["consensus_correct"] is False for r in selected),
                false_wan_routes=sum(r["modes"][minimum]["false_wan_route"] for r in selected),
                expected_wan_faces=sum(r["expected"].startswith("M") for r in selected),
                wan_routes=sum(r["modes"][minimum]["routed_to_wan_digit"] for r in selected),
                expected_identity_unscorable=sum(not r["modes"][minimum]["expected_identity_scorable"] for r in selected),
                routed_expected_identity_unscorable=sum(r["modes"][minimum]["routed_expected_identity_scorable"] is False for r in selected),
                routed_correct_identities=sum(r["modes"][minimum]["routed_identity_correct"] is True for r in selected))
    return dict(schema_version="new_match_symmetric_front_band_dev_v0_1" if front_band else ("new_match_lower_family_consensus_dev_v0_1" if lower_consensus else "new_match_family_route_falsification_dev_v0_1"), summary=summary, rows=rows,
        whole_bank_classes=sorted({t.tile_id for t in banks["whole"].templates}),
        routing_rule="whole-face source-disjoint SIFT winner's family; no label-selected family; absent winner abstains",
        lower_family_consensus_enabled=lower_consensus,
        lower_family_rule="lower half 72x96 binary WAN/NON_WAN bank; family support pools originals across tile classes; require both families eligible, positive ranking margins and whole/lower agreement; otherwise UNKNOWN" if lower_consensus else None,
        feature_views_are_independent_evidence=False,
        symmetric_front_band_enabled=front_band,
        merge_front_overlaps_enabled=merge_front_overlaps,
        front_band_failure_fallback=False,
        native_reference_feature_abstentions=native_reference_abstentions,
        private_template_feature_abstentions=private_feature_abstentions,
        private_loader_verification_contract_changed=False,
        reverse_old_m9_references_enabled=reverse_old_m9,
        reverse_reference_selection="all three previously frozen old frame 4794 faces" if reverse_old_m9 else None,
        reverse_reference_feature_rows=reverse_reference_rows,
        lower_feature_is_glyph_localized=False,
        known_feature_geometry_limit="vertical band preserves glyphs but can remove reference support and change class separation; not full plane rectification" if front_band else "review of three native reverse M9 faces shows the fixed lower half mostly covers gray side wall; raw face body is not the front glyph plane",
        score_is_calibrated_confidence=False, confidence_threshold_selected=False,
        crop_ratio_search_performed=False, upper_crop_fraction=0.5, upper_feature_size=[72,96],
        same_original_match_aliases_collapsed=sorted(alias), crop_hashes_and_source_registries_verified=True,
        native_video_hash_audit="inherited frozen reference intake; this evaluator verifies crop bytes and pin equality",
        reference_selection="previous frozen native 15-face pin; no new samples chosen by score",
        M8_reference_added=False, M8_draw_domain_is_public_meld_evidence=False,
        decision="reject global front-band feature replacement; retain geometry/numeral diagnostics only" if front_band else ("offline consensus hypothesis only; identity always UNKNOWN pending complete Wan support and confidence qualification" if lower_consensus else "reject winner-family routing as an automatic identity gate"),
        rejection_reasons=["non-Wan routing regressions", "reference coverage losses", "no calibrated confidence", "incomplete source-disjoint Wan alphabet"] if front_band else (["no calibrated confidence", "incomplete source-disjoint Wan alphabet"] if lower_consensus else ["non-Wan crops enter the Wan head", "unsupported M8 stress query ranks as M9", "SIFT winners provide no calibrated abstention"]),
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
    parser.add_argument("--lower-family-consensus", action="store_true")
    parser.add_argument("--front-band", action="store_true")
    parser.add_argument("--reverse-old-m9-references", action="store_true")
    parser.add_argument("--merge-front-overlaps", action="store_true")
    args = parser.parse_args()
    report = evaluate(root=args.repository_root, native_zip=args.native_reference_zip,
                      private_zip=args.private_template_zip, query_zips=args.query_zip,
                      lower_consensus=args.lower_family_consensus, front_band=args.front_band,
                      reverse_old_m9=args.reverse_old_m9_references,
                      merge_front_overlaps=args.merge_front_overlaps)
    args.output.write_text(json.dumps(report, separators=(",", ":"))+"\n")
    print(json.dumps(report["summary"]))


if __name__ == "__main__":
    main()
