"""Pinned manual visible-plane diagnostic; never an automatic edge repair."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
from unittest.mock import patch


def verify_plane_entries(groups, pin):
    from workspace.vision.public_meld_bracketed_front_band_probe import image_geometry_key
    if (pin.get("schema_version") != "reviewed_edge_visible_plane_pin_dev_v0_1"
            or pin.get("user_confirmed") is not False
            or pin.get("exact_face_plane_ground_truth") is not False
            or pin.get("complete_face_outline_claimed") is not False
            or pin.get("corners_frozen_before_identity_scores") is not True
            or pin.get("runtime_integration") is not False
            or pin.get("formal_promotion_evidence") is not False
            or any(pin.get(key) is not False for key in ("safe_for_runtime", "safe_for_hint", "safe_for_executor"))
            or pin.get("output_size") != [72, 96]):
        raise ValueError("manual geometry pin contract changed")
    available = {m["query_id"]: (m, image) for group in groups for m, image in group}
    entries = {}
    for entry in pin["entries"]:
        query = entry["query_id"]
        if query in entries or query not in available:
            raise ValueError("duplicate or missing manual query")
        meta, image = available[query]
        for name in ("source_sha256", "source_frame_pin", "crop_sha256"):
            if entry[name] != meta[name] or type(entry[name]) is not type(meta[name]):
                raise ValueError("manual source/frame/crop pin mismatch")
        if list(image.size) != entry["source_crop_size"]:
            raise ValueError("manual source dimensions mismatch")
        entries[query] = (entry, image_geometry_key(image))
    return entries


def compare_whole_classes(before, after):
    # The shared comparison also verifies every query/source/crop/label pin.
    from workspace.vision.compare_front_band_identity_reports import compare
    paired = compare(before, after)
    old = {r["query_id"]: r for r in before["rows"]}
    summary = {}
    for n in ("1", "2"):
        summary[n] = {}
        for packet in sorted({r["set"] for r in after["rows"]}):
            rows = [r for r in after["rows"] if r["set"] == packet]
            correct = lambda r: r["modes"][n]["family_ranking"]["top1_tile"] == r["expected"]
            summary[n][packet] = dict(faces=len(rows),
                correct_class_before=sum(correct(old[r["query_id"]]) for r in rows),
                correct_class_after=sum(correct(r) for r in rows),
                class_regressions=[r["query_id"] for r in rows if correct(old[r["query_id"]]) and not correct(r)])
    return dict(paired=paired, whole_class_summary=summary)


def evaluate(root, native_zip, private_zip, query_zips, pin_path, body_path, bracket_path,
             identity_output, comparison_output, geometry_output, review_directory=None):
    from PIL import Image
    from workspace.vision.evaluate_bracketed_front_band_probe import load_frozen_groups
    from workspace.vision import public_meld_bracketed_front_band_probe as bracket
    from workspace.vision.public_meld_edge_ridge_probe import prepare_edge_ridge_band
    from workspace.vision.public_meld_visible_face_rectification import rectify_reviewed_visible_face
    from workspace.vision.evaluate_new_match_family_route_probe import evaluate as evaluate_identity
    root = Path(root).resolve()
    groups, inputs = load_frozen_groups(root, native_zip, private_zip, query_zips,
                                        include_public_s789=True)
    pin = json.loads(Path(pin_path).read_text())
    entries = verify_plane_entries(groups, pin)
    if review_directory:
        review_directory = Path(review_directory); review_directory.mkdir(parents=True, exist_ok=True)
    public_group = next(group for group in groups
                        if group and group[0][0].get("packet") == "public_reference_controls")
    public_s9_meta, public_s9_image = next((meta, image) for meta, image in public_group
        if meta["query_id"] == "public_meld_s9")
    public_plane_pin = next(entry for entry in pin["entries"]
                            if entry["query_id"] == "public_meld_s9")
    reviewed_public_plane = dict(meta=dict(expected_visual_tile="S9", session=public_s9_meta["source_session"],
        sha256=public_s9_meta["source_sha256"], crop_pixel_sha256=public_s9_meta["crop_sha256"],
        label_id=public_s9_meta["label_id"]), image=public_s9_image,
        corners=public_plane_pin["corners_tl_tr_br_bl"], output_size=pin["output_size"])
    geometry_rows = []
    for group in groups:
        for index, (meta, image) in enumerate(group):
            peers = [(i, m["bounds"]) for j, (m, i) in enumerate(group) if j != index]
            direct, direct_audit = bracket.prepare_bracketed_front_band(image, meta["bounds"], peers)
            ridge, ridge_audit = prepare_edge_ridge_band(image)
            row = dict(**meta, bracketed_status="CANDIDATE" if direct is not None else "UNKNOWN",
                own_ridge_status="CANDIDATE" if ridge is not None else "UNKNOWN", own_ridge_audit=ridge_audit,
                additional_automatic_geometry=direct is None and ridge is not None)
            if meta["query_id"] in entries:
                entry, _ = entries[meta["query_id"]]
                reviewed = rectify_reviewed_visible_face(image, entry["corners_tl_tr_br_bl"], output_size=tuple(pin["output_size"]))
                buffer = io.BytesIO(); reviewed.save(buffer, format="PNG")
                row.update(reviewed_candidate_png_sha256=hashlib.sha256(buffer.getvalue()).hexdigest(),
                           reviewed_corners=entry["corners_tl_tr_br_bl"])
                if review_directory:
                    image.save(review_directory / (meta["query_id"]+"_source.png"))
                    reviewed.save(review_directory / (meta["query_id"]+"_reviewed.png"))
            geometry_rows.append(row)
    geometry = dict(schema_version="edge_ridge_and_reviewed_plane_geometry_dev_v0_1", rows=geometry_rows,
        query_count=len(geometry_rows), input_pin_sha256=inputs,
        reviewed_plane_pin_sha256=hashlib.sha256(Path(pin_path).read_bytes()).hexdigest(),
        additional_automatic_candidate_ids=[r["query_id"] for r in geometry_rows if r["additional_automatic_geometry"]],
        uncovered_query_count=sum(r["bracketed_status"]=="UNKNOWN" for r in geometry_rows),
        uncovered_ridge_reasons=dict(Counter(r["own_ridge_audit"]["reason"] for r in geometry_rows if r["bracketed_status"]=="UNKNOWN")),
        own_ridge_decision="reject as repair when it supplies no uncovered face candidates",
        original_frozen_query_count=sum(r["packet"] != "public_reference_controls" for r in geometry_rows),
        public_s789_control_count=sum(r["packet"] == "public_reference_controls" for r in geometry_rows),
        geometry_only=True, exact_face_plane_ground_truth=False, user_confirmed=False,
        manually_reviewed_candidates_not_automatic_success=True, crop_hashes_and_manifests_verified=True,
        previously_inspected=True, blind_holdout=False, formal_promotion_evidence=False,
        runtime_integration=False, safe_for_runtime=False, safe_for_hint=False, safe_for_executor=False)
    original_prepare = bracket.prepare_from_peer_context
    def manual_prepare(image, contexts, *, query_id=None, source_sha256=None):
        if query_id not in entries:
            return original_prepare(image, contexts, query_id=query_id, source_sha256=source_sha256)
        entry, pixels = entries[query_id]
        if entry["source_sha256"] != source_sha256 or bracket.image_geometry_key(image) != pixels:
            raise ValueError("manual feature input differs from verified source pixels")
        candidate = rectify_reviewed_visible_face(image, entry["corners_tl_tr_br_bl"], output_size=tuple(pin["output_size"]))
        return candidate, dict(failed=False, reason="manually_reviewed_visible_plane_candidate",
            source_sha256=source_sha256, source_frame_pin=entry["source_frame_pin"], crop_sha256=entry["crop_sha256"],
            corners=entry["corners_tl_tr_br_bl"], output_size=pin["output_size"], user_confirmed=False,
            exact_face_plane_ground_truth=False, automatic_geometry=False, tile_identity="UNKNOWN",
            runtime_integration=False, raw_feature_fallback=False,
            safe_for_runtime=False, safe_for_hint=False, safe_for_executor=False)
    with patch.object(bracket, "prepare_from_peer_context", manual_prepare):
        identity = evaluate_identity(root=root, native_zip=Path(native_zip), private_zip=Path(private_zip),
            query_zips=[Path(p) for p in query_zips], lower_consensus=True, front_band=True,
            merge_front_overlaps=True, bracketed_peer_band=True,
            reviewed_public_plane=reviewed_public_plane,
            reviewed_public_plane_as_query=True)
    identity.update(manually_reviewed_edge_plane_enabled=True,
        manual_edge_plane_query_ids=list(entries), manual_plane_pin_sha256=geometry["reviewed_plane_pin_sha256"],
        automatic_edge_repair=False, exact_face_plane_ground_truth=False, user_confirmed=False,
        manual_plane_coverage_is_partial=True, other_S9_references_keep_bracketed_features=True,
        public_S9_reference_uses_same_reviewed_plane=True,
        same_plane_transform_applied_to_reviewed_references_and_queries=True,
        decision="reviewed-plane ranking diagnostic only; reject automatic or global replacement")
    Path(identity_output).write_text(json.dumps(identity, separators=(",", ":"))+"\n")
    before = json.loads(Path(bracket_path).read_text()); body = json.loads(Path(body_path).read_text())
    comparison = dict(schema_version="reviewed_edge_plane_paired_comparison_dev_v0_1",
        input_sha256={name: hashlib.sha256(Path(path).read_bytes()).hexdigest() for name, path in
            (("bracketed", bracket_path), ("body", body_path), ("reviewed", identity_output), ("manual_pin", pin_path))},
        against_bracketed=compare_whole_classes(before, identity), against_body=compare_whole_classes(body, identity),
        targeted_edge_ranks=[dict(query_id=r["query_id"], source_sha256=r["sha256"], crop_sha256=r["crop_sha256"],
            expected=r["expected"], feature_preparation=r["feature_preparation"], modes=r["modes"],
            development_only=True, accuracy_evidence=False, formal_promotion_evidence=False)
            for r in identity["rows"] if r["query_id"] in entries],
        reviewed_public_s9_reverse_query_included=any(
            r["query_id"] == "public_meld_s9" for r in identity["rows"]),
        source_disjoint_ranking_required=True,
        targeted_ranks_are_accuracy_evidence=False,
        all_queries_kept_in_denominators=True, class_winners_are_qualified_identity=False,
        automatic_edge_repair=False, previously_inspected=True, blind_holdout=False,
        whole_lower_views_independent_evidence=False, formal_promotion_evidence=False,
        runtime_identity_threshold=0.82, runtime_integration=False,
        safe_for_runtime=False, safe_for_hint=False, safe_for_executor=False)
    Path(comparison_output).write_text(json.dumps(comparison, separators=(",", ":"))+"\n")
    Path(geometry_output).write_text(json.dumps(geometry, separators=(",", ":"))+"\n")
    return identity, geometry, comparison


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=".")
    for name in ("native-reference-zip", "private-template-zip", "plane-pin", "body-baseline", "bracketed-baseline", "identity-output", "comparison-output", "geometry-output"):
        parser.add_argument("--"+name, required=True)
    parser.add_argument("--query-zip", action="append", required=True)
    parser.add_argument("--review-directory")
    args = parser.parse_args()
    identity, geometry, comparison = evaluate(args.repository_root, args.native_reference_zip,
        args.private_template_zip, args.query_zip, args.plane_pin, args.body_baseline,
        args.bracketed_baseline, args.identity_output, args.comparison_output,
        args.geometry_output, args.review_directory)
    print(json.dumps(dict(automatic_additions=geometry["additional_automatic_candidate_ids"],
        identity_summary=identity["summary"], whole_class_summary=comparison["against_bracketed"]["whole_class_summary"])))


if __name__ == "__main__":
    main()
