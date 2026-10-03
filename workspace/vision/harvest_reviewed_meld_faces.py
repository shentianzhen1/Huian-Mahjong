"""Reproduce fixed, assistant-reviewed private face ROIs from existing videos.

Acquisition only: rectangular hand-picked ROIs do not certify automatic splitting,
independent match lineage, calibrated identity, or runtime acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED


def harvest(spec: dict, video_directory: str | Path, output_zip: str | Path) -> dict:
    import cv2
    from PIL import Image

    root = Path(video_directory).resolve()
    rows = []
    payloads = {}
    for source in spec["sources"]:
        path = (root / source["filename"]).resolve()
        if root not in path.parents or not path.is_file():
            raise ValueError("source must be a file beneath video directory")
        if hashlib.sha256(path.read_bytes()).hexdigest() != source["source_sha256"]:
            raise ValueError("source video SHA mismatch")
        cap = cv2.VideoCapture(str(path))
        try:
            for group in source["groups"]:
                tiles = group["reviewed_candidate_tiles"] if "reviewed_candidate_tiles" in group else [group["reviewed_candidate_tile"]] * len(group["face_bboxes"])
                if len(tiles) != len(group["face_bboxes"]):
                    raise ValueError("reviewed identity list must match face count")
                for frame in group["frame_indices"]:
                    if frame < 0 or frame >= int(cap.get(cv2.CAP_PROP_FRAME_COUNT)):
                        raise ValueError("reviewed frame outside source")
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
                    ok, bgr = cap.read()
                    if not ok or int(cap.get(cv2.CAP_PROP_POS_FRAMES)) != frame + 1:
                        raise ValueError("requested source frame not decoded")
                    image = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
                    for index, bbox in enumerate(group["face_bboxes"]):
                        x, y, width, height = bbox
                        if min(x, y) < 0 or min(width, height) <= 0 or x + width > image.width or y + height > image.height:
                            raise ValueError("reviewed crop outside source frame")
                        raw = io.BytesIO()
                        image.crop((x, y, x + width, y + height)).save(raw, format="PNG")
                        filename = f"faces/{group['group_id']}_{frame}_{index}.png"
                        if filename in payloads:
                            raise ValueError("duplicate face record")
                        payloads[filename] = raw.getvalue()
                        rows.append({"group_id": group["group_id"], "hand_index": group["hand_index"],
                            "source_sha256": source["source_sha256"], "frame_index": frame,
                            "decoded_time_seconds": frame / cap.get(cv2.CAP_PROP_FPS),
                            "match_group": spec["conservative_original_match_group"],
                            "source_session": source["source_session"], "face_index": index,
                            "bbox": bbox, "image_size": list(image.size),
                            "reviewed_candidate_tile": tiles[index],
                            "crop_file": filename,
                            "crop_sha256": hashlib.sha256(raw.getvalue()).hexdigest(),
                            "review": "assistant_visual_review_not_user_confirmation",
                            "manual_rectangular_roi": True, "automatic_splitter_verified": False,
                            "default_template_bank_eligible": False, "runtime_identity": "UNKNOWN"})
        finally:
            cap.release()
    report = {"schema_version": "existing_video_meld_face_intake_dev_v0_1",
        "spec": spec, "faces": rows, "face_count": len(rows),
        "group_count": len({row["group_id"] for row in rows}), "original_match_count": 1,
        "source_video_count": len(spec["sources"]),
        "manual_roi_warning": "Perspective margins include tile thickness and may include neighboring edge pixels; no automatic segmentation claim.",
        "independence_warning": "Clips, hands and frames from this eight-hand match count once; exclude both first-hand and eight-hand aliases when used in future scoring.",
        "source_disjoint_evaluation": False, "blind_validation": False,
        "formal_promotion_evidence": False, "runtime_integration": False,
        "safe_for_runtime": False, "safe_for_hint": False, "safe_for_executor": False}
    with ZipFile(output_zip, "w", ZIP_DEFLATED) as archive:
        archive.writestr("intake.json", json.dumps(report, indent=2) + "\n")
        for filename, raw in payloads.items():
            archive.writestr(filename, raw)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--video-directory", required=True)
    parser.add_argument("--output-zip", required=True)
    parser.add_argument("--output-report", required=True)
    args = parser.parse_args()
    report = harvest(json.loads(Path(args.spec).read_text()), args.video_directory, args.output_zip)
    Path(args.output_report).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("face_count", "group_count", "source_video_count", "original_match_count")}))


if __name__ == "__main__":
    main()
