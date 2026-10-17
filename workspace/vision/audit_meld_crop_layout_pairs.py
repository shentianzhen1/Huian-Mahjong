"""Inspect crop boundaries and frozen SIFT correspondence, without rescoring."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile


def features_with_positions(image):
    import cv2
    import numpy as np
    from workspace.vision import public_meld_identity_sift as frozen

    gray = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    gray = cv2.resize(gray, None, fx=frozen.SIFT_SCALE_FACTOR, fy=frozen.SIFT_SCALE_FACTOR, interpolation=cv2.INTER_CUBIC)
    gray = cv2.createCLAHE(clipLimit=frozen.SIFT_CLAHE_CLIP_LIMIT, tileGridSize=frozen.SIFT_CLAHE_TILE_GRID).apply(gray)
    keypoints, descriptors = cv2.SIFT_create(nfeatures=frozen.SIFT_NFEATURES).detectAndCompute(gray, None)
    expected = frozen._sift_descriptors(image)
    if expected is None:
        return None
    if descriptors is None or not np.array_equal(descriptors.astype("float32"), expected):
        raise ValueError("audit descriptors differ from frozen extractor")
    xy = np.array([[k.pt[0] / gray.shape[1], k.pt[1] / gray.shape[0]] for k in keypoints])
    return expected, xy


def bright_region_audit(image):
    """Reuse the existing normalization mask as a descriptive boundary probe.

    This mask includes neutral tile material. It is not a precise face polygon
    or a glyph detector, and touching a border does not prove clipped artwork.
    """
    import cv2
    import numpy as np

    rgb = np.asarray(image.convert("RGB"))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    mask = ((hsv[:, :, 1] < 110) & (hsv[:, :, 2] > 110)).astype("uint8") * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)
    y, x = np.nonzero(mask)
    if not len(x):
        return {"region_found": False, "precise_face_polygon_verified": False}
    height, width = mask.shape
    return {"region_found": True, "normalized_bbox": [float(x.min()/width), float(y.min()/height),
        float((x.max()+1-x.min())/width), float((y.max()+1-y.min())/height)],
        "touches_roi_edges": {"left": bool(x.min()==0), "right": bool(x.max()==width-1),
            "top": bool(y.min()==0), "bottom": bool(y.max()==height-1)},
        "roi_aspect_ratio": width/height, "mask_pixel_fraction": float(np.count_nonzero(mask)/mask.size),
        "precise_face_polygon_verified": False, "glyph_clipping_measured": False}


def pair_audit(query, reference):
    import cv2
    import numpy as np
    from workspace.vision import public_meld_identity_sift as frozen

    first, second = features_with_positions(query), features_with_positions(reference)
    if first is None or second is None:
        return {"issues": ["insufficient_descriptors"], "identity": "UNKNOWN"}
    qd, qxy = first
    rd, rxy = second
    matcher = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
    pairs = matcher.knnMatch(qd, rd, k=frozen.SIFT_KNN_K)
    good = [p[0] for p in pairs if len(p)==frozen.SIFT_KNN_K and p[0].distance < frozen.SIFT_RATIO_TEST*p[1].distance]
    ratio_count = len(good)
    if not good:
        good = sorted(matcher.match(qd, rd), key=lambda m:m.distance)[:frozen.SIFT_FALLBACK_RAW_MATCHES]
    best = {}
    for match in good:
        if match.trainIdx not in best or match.distance < best[match.trainIdx].distance:
            best[match.trainIdx] = match
    rows = []
    for index in sorted(best):
        match = best[index]
        a, b = qxy[match.queryIdx], rxy[match.trainIdx]
        rows.append({"query_index": match.queryIdx, "reference_index": index, "query_xy": a.tolist(),
            "reference_xy": b.tolist(), "distance": float(match.distance),
            "same_3x3_cell": bool(np.all(np.minimum(2,np.floor(a*3)) == np.minimum(2,np.floor(b*3))))})
    return {"ratio_match_count": ratio_count, "fallback_used": ratio_count==0,
        "unique_reference_matches": len(rows), "same_cell_matches": sum(r["same_3x3_cell"] for r in rows),
        "median_absolute_coordinate_delta": np.median([np.abs(np.array(r["query_xy"])-r["reference_xy"]) for r in rows],axis=0).tolist() if rows else None,
        "matches": rows, "query_bright_region": bright_region_audit(query),
        "reference_bright_region": bright_region_audit(reference),
        "global_alignment_fitted": False, "local_match_position_is_not_verified_glyph_correspondence": True,
        "identity": "UNKNOWN"}


def evaluate(*, hand8_intake_zip):
    import cv2
    from PIL import Image
    from workspace.vision.public_identity_labels import load_public_identity_manifest, approved_labels, pixel_bbox, verify_repository_files
    from workspace.vision.public_identity_shadow_v0_2 import load_development_sources

    label_path = "references/vision/2026-09-22/public_identity_labels_v0_1.json"
    source_path = "references/vision/2026-09-24/public_identity_source_groups.development.json"
    ledger_path = "references/vision/2026-10-03/hand8_s789_intake_v0_1.json"
    manifest = load_public_identity_manifest(label_path)
    if verify_repository_files(manifest, "."):
        raise ValueError("public source image integrity failed")
    labels = {l.label_id:l for l in approved_labels(manifest)}
    sources = load_development_sources(source_path)
    images = {}
    facts = {}
    for key in ("public_meld_p6", "eight_hand_h7_p456_p6_2", "public_meld_s9", "public_meld_s7"):
        label = labels[key]
        with Image.open(label.image_path) as source:
            image = source.convert("RGB")
        x,y,w,h = pixel_bbox(label,image.size)
        images[key] = image.crop((x,y,x+w,y+h))
        facts[key] = {"tile_id":label.tile_id,"source_sha256":label.source_sha256,
            "match_group":sources[label.source_session].match_group,"pixel_bbox":[x,y,w,h],
            "preparation":"direct_public_manifest_rectangle_without_face_rectification"}
    ledger = json.loads(Path(ledger_path).read_text())
    with ZipFile(hand8_intake_zip) as archive:
        if json.loads(archive.read("intake.json")) != ledger:
            raise ValueError("private query ledger mismatch")
        for frame in (4800,4806):
            face = next(r for r in ledger["faces"] if r["frame_index"]==frame and r["face_index"]==2)
            raw = archive.read(face["crop_file"])
            if hashlib.sha256(raw).hexdigest()!=face["crop_sha256"]:
                raise ValueError("private query crop SHA mismatch")
            key = f"hand8_s9_frame{frame}"
            with Image.open(io.BytesIO(raw)) as source:
                images[key] = source.convert("RGB")
            facts[key] = {"tile_id":"S9","source_sha256":face["source_sha256"],"match_group":face["match_group"],
                "pixel_bbox":face["bbox"],"crop_sha256":face["crop_sha256"],"preparation":"direct_assistant_reviewed_manual_rectangle"}
    pairs = [("public_meld_p6","eight_hand_h7_p456_p6_2"),("eight_hand_h7_p456_p6_2","public_meld_p6")]
    pairs += [(f"hand8_s9_frame{frame}",reference) for frame in (4800,4806) for reference in ("public_meld_s9","public_meld_s7")]
    rows = []
    for query, reference in pairs:
        if facts[query]["match_group"]==facts[reference]["match_group"] or facts[query]["source_sha256"]==facts[reference]["source_sha256"]:
            raise ValueError("layout audit pair must be source-disjoint")
        rows.append({"query_id":query,"reference_id":reference,"query":facts[query],"reference":facts[reference],
            "audit":pair_audit(images[query],images[reference])})
    return {"schema_version":"meld_crop_layout_pair_audit_dev_v0_1","pairs":rows,"opencv_version":cv2.__version__,
        "input_sha256":{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in (label_path,source_path,ledger_path)},
        "visual_review":"assistant: target glyphs readable; no apparent wrong-tile ROI; exact face corners not verified",
        "pipeline_observation":"SIFT templates and these probes use direct rectangles; ordinary FLAT query evaluator separately deskews/scales groups before splitting. These representations are not certified equivalent.",
        "conclusion":"Do not attribute all grid regressions to crop offsets. Repeated local patterns create ambiguous correspondences, and fixed ROI cells are not geometric verification.",
        "crop_pixels_changed":False,"rescore_performed":False,"global_transform_applied":False,
        "blind_validation":False,"runtime_integration":False,"formal_promotion_evidence":False,
        "safe_for_runtime":False,"safe_for_hint":False,"safe_for_executor":False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hand8-intake-zip",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    report=evaluate(hand8_intake_zip=args.hand8_intake_zip)
    Path(args.output).write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps([{k:r[k] for k in ("query_id","reference_id")} | {k:r["audit"][k] for k in ("unique_reference_matches","same_cell_matches")} for r in report["pairs"]]))


if __name__=="__main__":
    main()
