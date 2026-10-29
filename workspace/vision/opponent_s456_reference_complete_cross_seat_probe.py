"""Cross-seat stress probe for the frozen reference-completeness SIFT candidate.

This intentionally uses only repository-reviewed public-meld references so CI
can reproduce it without private pixels. It is a nonblind development stress
probe, not a holdout or Runtime promotion gate.
"""
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path


QUERY_MATCH_ALIASES = {
    "reviewed_match_2026_09_26_first_hand",
    "reviewed_match_2026_09_26_eight_hand",
}
EXPECTED_UNORDERED = {"S4", "S5", "S6"}
MINIMUM_OTHER_MATCH_GROUPS = 2


def run(repository_root: str | Path = ".") -> dict:
    from workspace.vision.evaluate_sift_symmetric_geometry_probe import normalize_single_face
    from workspace.vision.opponent_public_meld_mobilenet import (
        S456_QUERY, _load_query_frames, _prepare_query_faces,
    )
    from workspace.vision.public_identity_labels import (
        approved_labels, load_public_identity_manifest, pixel_bbox, verify_repository_files,
    )
    from workspace.vision.public_identity_shadow_v0_2 import load_development_sources
    from workspace.vision.sift_spatial_consistency_probe import (
        PositionedSift, reference_completeness_score,
    )
    from PIL import Image

    root = Path(repository_root).resolve()
    manifest = load_public_identity_manifest(
        root / "references/vision/2026-09-22/public_identity_labels_v0_1.json"
    )
    integrity = verify_repository_files(manifest, root)
    if integrity:
        raise ValueError("public identity source integrity failed: " + ",".join(integrity))
    sources = load_development_sources(
        root / "references/vision/2026-09-24/public_identity_source_groups.development.json"
    )

    probe = PositionedSift(local_window=True)
    references = []
    groups_by_tile = defaultdict(set)
    for label in approved_labels(manifest):
        if label.region != "public_meld":
            continue
        source = sources.get(label.source_session)
        if source is None or source.source_sha256 != label.source_sha256:
            raise ValueError("public meld source registry mismatch")
        if source.match_group in QUERY_MATCH_ALIASES:
            continue
        path = (root / label.image_path).resolve()
        with Image.open(path) as original:
            image = original.convert("RGB")
            x, y, w, h = pixel_bbox(label, image.size)
            crop = image.crop((x, y, x + w, y + h))
        normalized, _ = normalize_single_face(crop)
        descriptors = probe.extract(normalized) if normalized is not None else None
        if descriptors is None:
            continue
        references.append((label.tile_id, source.match_group, descriptors))
        groups_by_tile[label.tile_id].add(source.match_group)

    eligible = sorted(
        tile for tile, groups in groups_by_tile.items()
        if len(groups) >= MINIMUM_OTHER_MATCH_GROUPS
    )
    if eligible != ["P6", "S4"]:
        raise ValueError(f"public-only eligible class set drifted: {eligible}")

    frames = _load_query_frames(
        root / S456_QUERY.strip_path,
        len(S456_QUERY.source_frame_estimates),
        S456_QUERY,
    )
    prepared = _prepare_query_faces(frames, S456_QUERY)
    rows = []
    for frame_index, faces in zip(S456_QUERY.source_frame_estimates, prepared):
        face_rows = []
        for slot, face in enumerate(faces):
            normalized, audit = normalize_single_face(face)
            query = probe.extract(normalized) if normalized is not None else None
            scores = {}
            details = {}
            for tile_id, match_group, reference in references:
                if tile_id not in eligible:
                    continue
                forward = probe.score(query, reference)
                score = reference_completeness_score(forward, probe.last_audit)
                if score is None:
                    continue
                if score > scores.get(tile_id, float("-inf")):
                    scores[tile_id] = float(score)
                    details[tile_id] = {
                        "match_group": match_group,
                        "forward_score": float(forward),
                        "reference_support_fraction": probe.last_audit.get(
                            "reference_keypoints_supported_by_query_fraction"
                        ),
                        "weighted_score": float(score),
                    }
            ranking = sorted(scores.items(), key=lambda row: (-row[1], row[0]))
            face_rows.append({
                "slot": slot,
                "top1": ranking[0][0] if ranking and ranking[0][1] > 0 else None,
                "scores": ranking,
                "best_reference_details": details,
                "normalization": audit,
            })
        rows.append({
            "source_frame_estimate": frame_index,
            "faces": face_rows,
            "top1_tiles": [row["top1"] for row in face_rows],
            "s4_top1_slot_count": sum(row["top1"] == "S4" for row in face_rows),
        })

    return {
        "schema_version": "opponent_s456_reference_complete_cross_seat_probe_v0_1",
        "issue": 69,
        "candidate_commit": "69893a5c0ca18ccb3128b70ce9695fa48512f047",
        "score_policy": "spatial_window_affine_reference_complete",
        "query_review_id": S456_QUERY.review_id,
        "query_match_group": S456_QUERY.query_match_group,
        "query_match_aliases_excluded": sorted(QUERY_MATCH_ALIASES),
        "truth_scope": "human_confirmed_group_identity_only_no_left_to_right_truth",
        "expected_unordered_tiles": sorted(EXPECTED_UNORDERED),
        "minimum_other_match_groups": MINIMUM_OTHER_MATCH_GROUPS,
        "reference_policy": "repository_reviewed_public_meld_only_source_disjoint",
        "reference_group_counts": {
            tile: len(groups_by_tile[tile]) for tile in sorted(groups_by_tile)
        },
        "eligible_classes": eligible,
        "truth_class_eligibility": {
            tile: tile in eligible for tile in sorted(EXPECTED_UNORDERED)
        },
        "formal_group_scorable": all(tile in eligible for tile in EXPECTED_UNORDERED),
        "rows": rows,
        "diagnostic": {
            "frame_count": len(rows),
            "face_count": sum(len(row["faces"]) for row in rows),
            "frames_with_exactly_one_s4_top1": sum(
                row["s4_top1_slot_count"] == 1 for row in rows
            ),
            "frames_with_any_s4_top1": sum(
                row["s4_top1_slot_count"] >= 1 for row in rows
            ),
            "formal_correct": 0,
            "formal_wrong": 0,
            "formal_unknown": 15,
            "formal_exact_groups": 0,
            "formal_group_count": 5,
            "formal_abstention_reason": (
                "S5_and_S6_each_lack_two_other_original_match_groups"
            ),
        },
        "nonblind_cross_seat_stress_only": True,
        "parameter_retuning": False,
        "runtime_identity_threshold": 0.82,
        "runtime_integration": False,
        "changes_runtime_behavior": False,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = run(args.repository_root)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "eligible_classes": report["eligible_classes"],
        "truth_class_eligibility": report["truth_class_eligibility"],
        "formal_group_scorable": report["formal_group_scorable"],
        "diagnostic": report["diagnostic"],
        "top1_by_frame": [row["top1_tiles"] for row in report["rows"]],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
