"""Exercise the real fixed group-normalize/split chain on five Hand 8 frames."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from zipfile import ZipFile


def project_pinned_face_box(*, face_box, group_box, tight_box, normalized_size):
    """Project a pinned rectangular ROI into an unrotated normalized group."""
    x, y, width, height = face_box
    left, top, _, _ = group_box
    tight_x, tight_y, tight_width, tight_height = tight_box
    normalized_width, normalized_height = normalized_size
    if min(width, height, tight_width, tight_height, normalized_width, normalized_height) <= 0:
        raise ValueError("invalid fixed ROI projection dimensions")
    x0 = max(0, round((x - left - tight_x) * normalized_width / tight_width))
    x1 = min(normalized_width, round((x + width - left - tight_x) * normalized_width / tight_width))
    y0 = max(0, round((y - top - tight_y) * normalized_height / tight_height))
    y1 = min(normalized_height, round((y + height - top - tight_y) * normalized_height / tight_height))
    if x1 <= x0 or y1 <= y0:
        raise ValueError("pinned ROI maps outside normalized group")
    return x0, y0, x1 - x0, y1 - y0


def evaluate(*, intake_zip, private_template_zip, video_path):
    from collections import defaultdict
    import cv2
    import numpy as np
    import PIL
    from PIL import Image
    from workspace.vision.public_meld_identity_sift import (
        PublicMeldSiftBank, PublicMeldSiftTemplate, _sift_descriptors,
        build_public_meld_sift_bank,
    )
    from workspace.vision.public_meld_private_sift_loader import augment_public_meld_sift_bank_from_private_zip
    from workspace.vision.public_identity_labels import load_public_identity_manifest
    from workspace.vision.public_identity_shadow_v0_2 import SourceGroup
    from workspace.vision.public_meld_geometry_normalization import (
        FLAT, normalize_public_meld_crop, split_flat_meld_faces,
    )
    from workspace.vision.public_tile_detector import PublicGeometryCandidate
    from workspace.vision.evaluate_sift_symmetric_geometry_probe import normalize_single_face

    root = Path(".")
    spec_path = root / "references/vision/2026-10-03/hand8_s789_harvest_spec_v0_1.json"
    spec = json.loads(spec_path.read_text())
    source = spec["sources"][0]
    video = Path(video_path)
    video_sha = hashlib.sha256(video.read_bytes()).hexdigest()
    if video_sha != source["source_sha256"]:
        raise ValueError("Hand 8 source video SHA mismatch")
    intake_pin_path = root / "references/vision/2026-10-03/hand8_s789_intake_v0_1.json"
    pinned = json.loads(intake_pin_path.read_text())
    face_by_frame = {}
    with ZipFile(intake_zip) as archive:
        intake = json.loads(archive.read("intake.json"))
        if intake != pinned:
            raise ValueError("private query ledger differs from repository pixel/hash pin")
        for row in intake["faces"]:
            raw = archive.read(row["crop_file"])
            if hashlib.sha256(raw).hexdigest() != row["crop_sha256"]:
                raise ValueError("private query face SHA mismatch")
            face_by_frame.setdefault(row["frame_index"], []).append(row)

    manifest = load_public_identity_manifest(root / "references/vision/2026-09-22/public_identity_labels_v0_1.json")
    bank, loaded = build_public_meld_sift_bank(manifest, root,
        root / "references/vision/2026-09-24/public_identity_source_groups.development.json"), None
    bank, loaded = augment_public_meld_sift_bank_from_private_zip(bank,
        private_zip_path=private_template_zip,
        recovery_result_path=root / "references/vision/2026-10-02/public_meld_private_recovery_result_v0_3.json",
        repository_root=root)
    aliases = set(spec["excluded_same_match_aliases"])
    sources = {key: SourceGroup(s.session, s.source_sha256,
        spec["conservative_original_match_group"] if s.match_group in aliases else s.match_group)
        for key, s in bank.sources.items()}
    for source_row in spec["sources"]:
        sources[source_row["source_session"]] = SourceGroup(source_row["source_session"],
            source_row["source_sha256"], spec["conservative_original_match_group"])
    templates = tuple(PublicMeldSiftTemplate(t.tile_id, t.source_session, t.source_sha256,
        sources[t.source_session].match_group, t.descriptors) for t in bank.templates
        if t.match_group not in aliases)
    bank = PublicMeldSiftBank(sources, templates)

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError("cannot open pinned Hand 8 source video")
    rows, geometry = [], []
    try:
        for frame in pinned["spec"]["sources"][0]["groups"][0]["frame_indices"]:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
            ok, bgr = cap.read()
            if not ok or int(cap.get(cv2.CAP_PROP_POS_FRAMES)) != frame + 1:
                raise ValueError("pinned frame decode mismatch")
            image = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
            rows_for_frame = sorted(face_by_frame[frame], key=lambda r: r["face_index"])
            if len(rows_for_frame) != 3 or [r["face_index"] for r in rows_for_frame] != [0, 1, 2]:
                raise ValueError("pinned group needs exactly the three ledger faces")
            # Group ROI is mechanically fixed to the union of the three already
            # pinned face ROIs; no frame-specific crop or identity search.
            boxes = [tuple(r["bbox"]) for r in rows_for_frame]
            left, top = min(b[0] for b in boxes), min(b[1] for b in boxes)
            right = max(b[0] + b[2] for b in boxes)
            bottom = max(b[1] + b[3] for b in boxes)
            candidate = PublicGeometryCandidate((left, top, right-left, bottom-top),
                (0., 0., 1., 1.), "bottom_group", 1., 1., frame, "hand8_s789")
            normalized = normalize_public_meld_crop(image, candidate)
            faces = split_flat_meld_faces(normalized) if normalized.analysis.stack_state == FLAT else ()
            if len(faces) != 3:
                raise ValueError(f"frame {frame}: actual group pipeline abstained: {normalized.analysis.stack_state}")
            raw_boundaries = [round((right - left) * index / 3) for index in range(4)]
            raw_equal_faces = [image.crop((left + raw_boundaries[index], top,
                left + raw_boundaries[index + 1], bottom)) for index in range(3)]
            raw_equal_descriptors = [_sift_descriptors(normalize_single_face(face)[0])
                for face in raw_equal_faces]
            split_raw_descriptors = [_sift_descriptors(face) for face in faces]
            ids = [_sift_descriptors(normalize_single_face(face)[0]) for face in faces]
            if any(desc is None for desc in ids):
                raise ValueError(f"frame {frame}: split face has insufficient descriptors")
            # Boundary-only counterfactual: map the already pinned/manual ROI
            # edges into the very same normalized group image. No pixel/frame
            # search; overlapping manual ROIs remain overlapping for diagnosis.
            tight_box = normalized.analysis.tight_bbox_in_group
            if tight_box is None or normalized.image is None:
                raise ValueError("fixed ROI projection requires a normalized image and tight bbox")
            review_faces = []
            review_raw_descriptors = []
            mapped_boxes = []
            if abs(normalized.analysis.rotation_degrees) > 0.01:
                raise ValueError("fixed ROI coordinate projection only supports the pinned zero-rotation case")
            for box in boxes:
                x0, y0, w, h = project_pinned_face_box(
                    face_box=box,
                    group_box=(left, top, right-left, bottom-top),
                    tight_box=tight_box,
                    normalized_size=normalized.image.size,
                )
                x1, y1 = x0 + w, y0 + h
                mapped_boxes.append([x0, y0, w, h])
                raw_face = normalized.image.crop((x0, y0, x1, y1))
                review_raw_descriptors.append(_sift_descriptors(raw_face))
                face, _ = normalize_single_face(raw_face)
                review_faces.append(_sift_descriptors(face))
            if any(desc is None for desc in review_faces):
                raise ValueError(f"frame {frame}: reviewed-boundary split lacks descriptors")
            geometry.append({"frame": frame, "group_bbox": [left, top, right-left, bottom-top],
                "stack_state": normalized.analysis.stack_state,
                "normalized_group_size": list(normalized.image.size),
                "split_face_sizes": [list(f.size) for f in faces],
                "manual_roi_mapped_split_boxes": mapped_boxes,
                "rotation_degrees": normalized.analysis.rotation_degrees,
                "tight_bbox_in_group": normalized.analysis.tight_bbox_in_group,
                "face_identity_crop_sha256": [r["crop_sha256"] for r in rows_for_frame],
                "input_faces_were_manual_rois_not_verified_splitter_outputs": all(not r["automatic_splitter_verified"] for r in rows_for_frame)})
            for i, (row, group_descriptors, reviewed_descriptors) in enumerate(zip(rows_for_frame, ids, review_faces)):
                with ZipFile(intake_zip) as archive:
                    with Image.open(io.BytesIO(archive.read(row["crop_file"]))) as direct:
                        direct_face, _ = normalize_single_face(direct.convert("RGB"))
                        direct_descriptors = _sift_descriptors(direct_face)
                group_face, _ = normalize_single_face(faces[i])
                common_width = max(direct_face.width, group_face.width)
                direct_pixels = np.asarray(direct_face.resize((common_width, 96), Image.Resampling.LANCZOS), dtype=np.float32)
                group_pixels = np.asarray(group_face.resize((common_width, 96), Image.Resampling.LANCZOS), dtype=np.float32)
                direct_gray = cv2.cvtColor(direct_pixels.astype("uint8"), cv2.COLOR_RGB2GRAY).astype(np.float32)
                group_gray = cv2.cvtColor(group_pixels.astype("uint8"), cv2.COLOR_RGB2GRAY).astype(np.float32)
                correlation = float(np.corrcoef(direct_gray.ravel(), group_gray.ravel())[0, 1])
                expected = row["reviewed_candidate_tile"]
                row_scores = {}
                for mode, query in (("direct_face_symmetric_geometry", direct_descriptors),
                                    ("raw_group_equal_thirds_then_face_geometry", raw_equal_descriptors[i]),
                                    ("group_normalize_equal_thirds_no_second_normalization", split_raw_descriptors[i]),
                                    ("group_normalize_split_then_face_geometry", group_descriptors),
                                    ("group_normalize_manual_roi_no_second_normalization", review_raw_descriptors[i]),
                                    ("group_normalize_manual_roi_boundary_counterfactual", reviewed_descriptors)):
                    by_class_group = defaultdict(dict)
                    if query is not None:
                        source_lineage = sources[row["source_session"]]
                        for template in bank.templates:
                            if template.match_group == source_lineage.match_group or template.source_sha256 == row["source_sha256"]:
                                continue
                            score = frozen_score(query, template.descriptors)
                            if score is not None:
                                by_class_group[template.tile_id][template.match_group] = max(
                                    by_class_group[template.tile_id].get(template.match_group, float("-inf")), score)
                    best = sorted((tile, sorted(scores.values(), reverse=True)[0])
                        for tile, scores in by_class_group.items() if scores)
                    best.sort(key=lambda item: (-item[1], item[0]))
                    row_scores[mode] = {"top1": best[0][0] if best else None,
                        "top1_score": round(float(best[0][1]), 8) if best else None,
                        "runner_up_tile": best[1][0] if len(best) > 1 else None,
                        "runner_up_score": round(float(best[1][1]), 8) if len(best) > 1 else None,
                        "scorable": expected in by_class_group,
                        "query_descriptor_count": len(query) if query is not None else 0,
                        "expected_class_score": sorted(by_class_group[expected].values(), reverse=True)[0]
                            if expected in by_class_group else None,
                        "top1_correct": bool(best and best[0][0] == expected) if expected in by_class_group else None}
                rows.append({"frame": frame, "face_index": i, "expected": expected, "modes": row_scores})
                rows[-1]["processed_face_comparison"] = {
                    "manual_face_normalized_size": list(direct_face.size),
                    "group_split_face_normalized_size": list(group_face.size),
                    "common_comparison_size": [common_width, 96],
                    "mae_rgb_0_255": round(float(np.mean(np.abs(direct_pixels-group_pixels))), 5),
                    "grayscale_pixel_correlation_after_width_alignment": round(correlation, 6)}
    finally:
        cap.release()
    summaries = {}
    for mode in ("direct_face_symmetric_geometry",
                 "raw_group_equal_thirds_then_face_geometry",
                 "group_normalize_equal_thirds_no_second_normalization",
                 "group_normalize_split_then_face_geometry",
                 "group_normalize_manual_roi_no_second_normalization",
                 "group_normalize_manual_roi_boundary_counterfactual"):
        selected = [r for r in rows if r["modes"][mode]["scorable"]]
        summaries[mode] = {"faces": len(rows), "scorable_faces": len(selected),
            "correct_when_scorable": sum(r["modes"][mode]["top1_correct"] is True for r in selected),
            "face_top1_rows_correct": sum(r["modes"][mode]["top1_correct"] is True for r in rows),
            "legal_groups_scorable": sum(all(r["modes"][mode]["scorable"] for r in rows if r["frame"] == frame) for frame in sorted({r["frame"] for r in rows})),
            "legal_groups_correct": sum({r["modes"][mode]["top1"] for r in rows if r["frame"] == frame} == {"S7", "S8", "S9"} for frame in sorted({r["frame"] for r in rows}))}
    group_mode = summaries["group_normalize_split_then_face_geometry"]
    direct_mode = summaries["direct_face_symmetric_geometry"]
    for tile in ("S7", "S8", "S9"):
        selected = [r for r in rows if r["expected"] == tile]
        summaries.setdefault("processed_pixel_difference_by_tile", {})[tile] = {
            "face_rows": len(selected),
            "mean_rgb_mae_0_255_after_width_alignment": round(float(np.mean([
                r["processed_face_comparison"]["mae_rgb_0_255"] for r in selected])), 5),
            "mean_grayscale_correlation_after_width_alignment": round(float(np.mean([
                r["processed_face_comparison"]["grayscale_pixel_correlation_after_width_alignment"] for r in selected])), 6),
            "direct_correct": sum(r["modes"]["direct_face_symmetric_geometry"]["top1_correct"] is True for r in selected),
            "group_split_correct": sum(r["modes"]["group_normalize_split_then_face_geometry"]["top1_correct"] is True for r in selected)}
    decision = ("reject_group_pipeline_candidate_on_fixed_hand8_queries"
        if group_mode["legal_groups_correct"] < direct_mode["legal_groups_correct"]
        or group_mode["correct_when_scorable"] < direct_mode["correct_when_scorable"]
        else "development_only_no_promotion")
    return {"schema_version": "sift_group_split_geometry_probe_dev_v0_2",
        "geometry": geometry, "query_count": len(rows),
        "rows": rows, "summary": summaries,
        "source_sha256": video_sha, "private_template_load": loaded,
        "input_sha256": {str(intake_pin_path): hashlib.sha256(intake_pin_path.read_bytes()).hexdigest(),
            str(spec_path): hashlib.sha256(spec_path.read_bytes()).hexdigest(),
            "workspace/vision/public_meld_geometry_normalization.py": hashlib.sha256(Path("workspace/vision/public_meld_geometry_normalization.py").read_bytes()).hexdigest(),
            "workspace/vision/public_meld_identity_sift.py": hashlib.sha256(Path("workspace/vision/public_meld_identity_sift.py").read_bytes()).hexdigest()},
        "group_crop_policy": "bounding union of three SHA-pinned face ROIs",
        "boundary_counterfactual": "same normalized group image cropped using fixed ledger ROI edges mapped into normalized coordinates",
        "stage_factorial": "equal thirds versus pinned manual ROI boundaries, each with or without second face normalization; frozen SIFT scorer and templates unchanged",
        "raw_group_equal_thirds_counterfactual": "equal third boundaries in raw union crop before any group normalization, then same single-face normalization as direct baseline",
        "dependency_versions": {"opencv": cv2.__version__, "numpy": np.__version__, "pillow": PIL.__version__},
        "boundary_counterfactual_is_automatic_splitter": False,
        "boundary_counterfactual_is_new_training_data": False,
        "identity_scoring_completed": True, "candidate_decision": decision,
        "minimum_other_original_match_groups": 1,
        "identity_top1_is_development_ranking_not_runtime_confidence": True,
        "manual_face_boundary_review": False, "geometry_and_identity_reported_separately": True,
        "runtime_integration": False, "safe_for_runtime": False, "safe_for_hint": False, "safe_for_executor": False}


def frozen_score(first, second):
    """Byte-for-byte scoring policy from the frozen development SIFT matcher."""
    import cv2
    import numpy as np
    from workspace.vision.public_meld_identity_sift import (
        SIFT_FALLBACK_RAW_MATCHES, SIFT_KNN_K, SIFT_RATIO_TEST,
    )
    if first is None or second is None or len(first) < 2 or len(second) < 2:
        return None
    matcher = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
    pairs = matcher.knnMatch(first, second, k=SIFT_KNN_K)
    distances = [float(p[0].distance) for p in pairs if len(p) == SIFT_KNN_K
        and p[0].distance < SIFT_RATIO_TEST * p[1].distance]
    if not distances:
        raw = matcher.match(first, second)
        if not raw:
            return None
        distances = sorted(float(m.distance) for m in raw)[:SIFT_FALLBACK_RAW_MATCHES]
    return float(len(distances) / (1.0 + np.mean(distances)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intake-zip", required=True)
    parser.add_argument("--private-template-zip", required=True)
    parser.add_argument("--video", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if importlib.util.find_spec("cv2") is None:
        parser.error("OpenCV is missing from this Python environment; install the project's optional vision dependencies: python -m pip install -e '.[vision]'")
    if Path(args.output).exists():
        parser.error("output already exists; choose a new development report path to preserve prior evidence")
    report = evaluate(intake_zip=args.intake_zip, private_template_zip=args.private_template_zip, video_path=args.video)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"query_count": report["query_count"], "summary": report["summary"], "geometry": report["geometry"]}))


if __name__ == "__main__":
    main()
