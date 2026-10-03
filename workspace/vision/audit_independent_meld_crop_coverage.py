"""Development-only source-locked geometry audit on the independent 14.mp4.

The approved crop locates and scores the reviewed group; it never constructs
candidate boxes. Scores measure rectangle coverage, not tile identity or
pixel-exact face-body coverage. Keep all footage out of the public repository.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


CALIBRATION = Path("references/vision/2026-09-22/public_detector_calibration_v0_1.json")
TEMPLATE = Path("references/vision/2026-09-30/public_meld_crops/special_14_s234.jpg")
SAMPLE_ID = "special14_player_chi_s234_088s"
FRAMES = (2549, 2552, 2555)


def rectangle_coverage(candidate: tuple[int, ...], target: tuple[int, ...]) -> float:
    """Fraction of the target area covered; useful only as a geometry proxy."""
    left, top = max(candidate[0], target[0]), max(candidate[1], target[1])
    right, bottom = min(candidate[2], target[2]), min(candidate[3], target[3])
    return max(0, right - left) * max(0, bottom - top) / (
        (target[2] - target[0]) * (target[3] - target[1])
    )


def audit(video_path: str | Path) -> dict:
    import cv2
    from PIL import Image
    from workspace.vision.evaluate_sift_detector_body_boundary_probe import raw_face_boxes
    from workspace.vision.public_tile_detector import detect_public_tile_geometry

    samples = json.loads(CALIBRATION.read_text(encoding="utf-8"))["samples"]
    sample = next(row for row in samples if row["sample_id"] == SAMPLE_ID)
    source_sha = hashlib.sha256(Path(video_path).read_bytes()).hexdigest()
    if source_sha != sample["source_sha256"]:
        raise ValueError("source SHA mismatch")
    template_sha = hashlib.sha256(TEMPLATE.read_bytes()).hexdigest()
    if template_sha != sample["image_sha256"]:
        raise ValueError("reviewed crop SHA mismatch")
    template = cv2.imread(str(TEMPLATE))
    height, width = template.shape[:2]
    cap = cv2.VideoCapture(str(video_path))
    rows = []
    try:
        for frame in FRAMES:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
            ok, bgr = cap.read()
            if not ok or int(cap.get(cv2.CAP_PROP_POS_FRAMES)) != frame + 1:
                raise ValueError("frame decode mismatch")
            scores = cv2.matchTemplate(bgr, template, cv2.TM_CCOEFF_NORMED)
            _, match_score, _, (tx, ty) = cv2.minMaxLoc(scores)
            if match_score < 0.99:
                raise ValueError("reviewed crop does not locate in source frame")
            image = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
            # Equal-thirds are only a face-rectangle review proxy, not manual
            # tile-body ground truth and not candidate crop input.
            targets = tuple((tx + round(width * index / 3), ty,
                             tx + round(width * (index + 1) / 3), ty + height)
                            for index in range(3))
            detected = detect_public_tile_geometry(image, frame=frame)
            candidates = [candidate for candidate in detected.candidates
                          if candidate.geometry_kind == "bottom_group"
                          and rectangle_coverage((candidate.pixel_bbox[0], candidate.pixel_bbox[1],
                              candidate.pixel_bbox[0] + candidate.pixel_bbox[2],
                              candidate.pixel_bbox[1] + candidate.pixel_bbox[3]),
                              (tx, ty, tx + width, ty + height)) > 0.5]
            if len(candidates) != 1:
                raise ValueError("reviewed group has no unique detector candidate")
            candidate = candidates[0]
            modes = {}
            for name, body_context, seam_context, outer in (
                ("detector_raw", False, 0, False),
                ("detector_seam2", False, 2, False),
                ("body_context_no_seam", True, 0, False),
                ("body_context_seam2", True, 2, False),
                ("outer_body_seam2", False, 2, True),
            ):
                boxes, geometry = raw_face_boxes(image, candidate,
                    body_context=body_context, seam_context=seam_context, outer_body=outer)
                if len(boxes) != 3:
                    modes[name] = {"abstained": True, "reason": geometry.get("reason")}
                    continue
                modes[name] = {"abstained": False,
                    "face_rect_coverage": [round(rectangle_coverage(box, target), 6)
                                           for box, target in zip(boxes, targets)],
                    "face_boxes": [list(box) for box in boxes],
                    "raw_group_xyxy": geometry["raw_group_xyxy"]}
            rows.append({"frame": frame, "template_match_score": round(match_score, 6),
                "reviewed_crop_xyxy": [tx, ty, tx + width, ty + height],
                "detector_bbox": list(candidate.pixel_bbox), "modes": modes})
    finally:
        cap.release()
    return {"schema_version": "independent_meld_crop_coverage_dev_v0_1",
        "source_sha256": source_sha, "reviewed_crop_sha256": template_sha,
        "source_original_match_group": "reviewed_recording_14", "rows": rows,
        "target_provenance": "SHA-pinned reviewed crop located in SHA-pinned source; equal-third rectangle proxy",
        "reviewed_crop_used_for_candidate_edges": False,
        "identity_accuracy_measured": False,
        "this_is_not_pixel_exact_visible_tile_body_coverage": True,
        "parameters_selected_after_development_inspection": True,
        "formal_holdout": False, "runtime_integration": False,
        "safe_for_runtime": False, "safe_for_hint": False, "safe_for_executor": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(audit(args.video), indent=2) + "\n", encoding="utf-8")
