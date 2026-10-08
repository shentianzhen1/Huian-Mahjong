"""Exact-coordinate audit of fixed Hand 8 manual ROIs vs equal-third splits."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def audit(*, intake_path: str | Path, geometry_report_path: str | Path) -> dict:
    intake_path = Path(intake_path)
    geometry_report_path = Path(geometry_report_path)
    intake = json.loads(intake_path.read_text())
    geometry = json.loads(geometry_report_path.read_text())
    faces_by_frame: dict[int, list[dict]] = {}
    for row in intake["faces"]:
        faces_by_frame.setdefault(row["frame_index"], []).append(row)
    geometry_by_frame = {row["frame"]: row for row in geometry["geometry"]}
    output = []
    for frame in (4794, 4797, 4800, 4803, 4806):
        faces = sorted(faces_by_frame[frame], key=lambda row: row["face_index"])
        if len(faces) != 3 or [row["face_index"] for row in faces] != [0, 1, 2]:
            raise ValueError(f"frame {frame}: expected the three pinned manual face ROIs")
        group = geometry_by_frame[frame]
        gx, gy, gw, gh = group["group_bbox"]
        tx, ty, tw, th = group["tight_bbox_in_group"]
        nw, nh = group["normalized_group_size"]
        if nw % 3 or group["stack_state"] != "FLAT":
            raise ValueError("fixed equal-third audit requires divisible width and FLAT geometry")
        mapped = []
        for face in faces:
            x, y, w, h = face["bbox"]
            x0 = round((x - gx - tx) * nw / tw)
            x1 = round((x + w - gx - tx) * nw / tw)
            y0 = round((y - gy - ty) * nh / th)
            y1 = round((y + h - gy - ty) * nh / th)
            x0, x1 = max(0, x0), min(nw, x1)
            y0, y1 = max(0, y0), min(nh, y1)
            mapped.append([x0, y0, x1 - x0, y1 - y0])
        width = nw // 3
        equal = [[i * width, 0, width, nh] for i in range(3)]
        rows = []
        for index, (manual, automatic) in enumerate(zip(mapped, equal)):
            mx0, _, mw, _ = manual
            ax0, _, aw, _ = automatic
            mx1, ax1 = mx0 + mw, ax0 + aw
            missing = []
            if ax0 > mx0:
                missing.append([mx0, min(ax0, mx1)])
            if ax1 < mx1:
                missing.append([max(ax1, mx0), mx1])
            rows.append({"face_index": index, "reviewed_tile_candidate": faces[index]["reviewed_candidate_tile"],
                "manual_roi_mapped_bbox": manual, "equal_third_bbox": automatic,
                "manual_roi_x_intervals_omitted_by_equal_thirds": [pair for pair in missing if pair[0] < pair[1]],
                "omitted_normalized_x_pixels": sum(b - a for a, b in missing if a < b)})
        output.append({"frame": frame, "source_sha256": faces[0]["source_sha256"],
            "group_bbox": [gx, gy, gw, gh], "normalized_group_size": [nw, nh],
            "faces": rows,
            "overlap_manual_roi_faces_0_1_x": [max(mapped[0][0], mapped[1][0]), min(mapped[0][0]+mapped[0][2], mapped[1][0]+mapped[1][2])],
            "overlap_manual_roi_faces_1_2_x": [max(mapped[1][0], mapped[2][0]), min(mapped[1][0]+mapped[1][2], mapped[2][0]+mapped[2][2])]})
    if any(row["source_sha256"] != output[0]["source_sha256"] for row in output):
        raise ValueError("frame set spans unexpected source videos")
    return {"schema_version": "hand8_fixed_manual_vs_equal_split_boundary_audit_dev_v0_1",
        "frames": output,
        "input_sha256": {str(intake_path): hashlib.sha256(intake_path.read_bytes()).hexdigest(),
            str(geometry_report_path): hashlib.sha256(geometry_report_path.read_bytes()).hexdigest()},
        "mapping": "manual frame-space bbox edges linearly projected through recorded zero-rotation tight group bbox to normalized group pixels",
        "search_performed": False, "source_pixels_modified": False,
        "identity_rerank_performed": False, "manual_rois_are_exact_tile_polygons": False,
        "causal_claim": False, "runtime_integration": False,
        "safe_for_runtime": False, "safe_for_hint": False, "safe_for_executor": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intake", required=True)
    parser.add_argument("--geometry-report", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = audit(intake_path=args.intake, geometry_report_path=args.geometry_report)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps([{
        "frame": row["frame"],
        "omitted_pixels": [face["omitted_normalized_x_pixels"] for face in row["faces"]],
        "manual_roi_mapped_bboxes": [face["manual_roi_mapped_bbox"] for face in row["faces"]],
        "equal_thirds": [face["equal_third_bbox"] for face in row["faces"]],
    } for row in report["frames"]]))


if __name__ == "__main__":
    main()
