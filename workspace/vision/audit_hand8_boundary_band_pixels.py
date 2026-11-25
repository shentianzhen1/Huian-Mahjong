"""Audit fixed Hand 8 boundary-only pixel bands without optional OpenCV."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile


def evaluate(*, intake_zip: str | Path, geometry_report: str | Path) -> dict:
    import numpy as np
    from PIL import Image

    pin = Path("references/vision/2026-10-03/hand8_s789_intake_v0_1.json")
    expected = json.loads(pin.read_text())
    geometry = json.loads(Path(geometry_report).read_text())
    if geometry["source_sha256"] != expected["spec"]["sources"][0]["source_sha256"]:
        raise ValueError("geometry report source differs from pinned Hand 8 source")
    frames = {row["frame"]: row for row in geometry["geometry"]}
    records = []
    with ZipFile(intake_zip) as archive:
        intake = json.loads(archive.read("intake.json"))
        if intake != expected:
            raise ValueError("private intake differs from pinned metadata")
        for row in intake["faces"]:
            frame = row["frame_index"]
            record = frames[frame]
            if record["rotation_degrees"] != 0 or record["tight_bbox_in_group"] != [0, 0, 135, 60]:
                raise ValueError("raw boundary audit only applies to pinned unrotated geometry")
            if record["group_bbox"] != [248, 441, 135, 62] or record["normalized_group_size"] != [216, 96]:
                raise ValueError("unexpected pinned group geometry")
            if record["face_identity_crop_sha256"][row["face_index"]] != row["crop_sha256"]:
                raise ValueError("geometry and intake face SHA differ")
            raw = archive.read(row["crop_file"])
            if hashlib.sha256(raw).hexdigest() != row["crop_sha256"]:
                raise ValueError("private face SHA mismatch")
            with Image.open(io.BytesIO(raw)) as image:
                pixels = np.asarray(image.convert("RGB"), dtype=np.int16)
            index = row["face_index"]
            equal_boundaries = (248, 293, 338, 383)
            x, _, width, _ = row["bbox"]
            bands = [(x, min(x + width, equal_boundaries[index])),
                     (max(x, equal_boundaries[index + 1]), x + width)]
            for left, right in bands:
                if right <= left:
                    continue
                # The first/last raster rows include decorative tile edges;
                # count chromatic pixels in the face body separately.
                body = pixels[1:-1, left - x:right - x]
                chromatic = np.ptp(body, axis=2) > 45
                records.append({"frame": frame, "face_index": index,
                    "reviewed_candidate_tile": row["reviewed_candidate_tile"],
                    "omitted_raw_x_interval": [left, right],
                    "omitted_raw_column_count": right - left,
                    "face_body_chromatic_pixels_span_gt_45": int(chromatic.sum()),
                    "face_body_pixel_count": int(chromatic.size)})
    nine = [row for row in records if row["reviewed_candidate_tile"] == "S9"]
    return {"schema_version": "hand8_boundary_band_pixels_dev_v0_1",
        "source_sha256": geometry["source_sha256"],
        "pinned_geometry_report_sha256": hashlib.sha256(Path(geometry_report).read_bytes()).hexdigest(),
        "pinned_intake_ledger_sha256": hashlib.sha256(pin.read_bytes()).hexdigest(),
        "method": "unrotated raw-frame inverse of recorded 216-to-135 normalization; face body excludes first/last raster rows; chromatic when max(R,G,B)-min(R,G,B)>45",
        "records": records, "s9_omitted_band_count": len(nine),
        "s9_chromatic_body_pixels_in_omitted_bands": sum(row["face_body_chromatic_pixels_span_gt_45"] for row in nine),
        "manual_rois_are_not_verified_tile_polygons": True,
        "chromatic_test_does_not_prove_glyph_absence_or_sift_causality": True,
        "opencv_identity_rerank_performed": False,
        "runtime_integration": False, "safe_for_runtime": False,
        "safe_for_hint": False, "safe_for_executor": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intake-zip", required=True)
    parser.add_argument("--geometry-report", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        parser.error("output exists; preserve earlier evidence")
    report = evaluate(intake_zip=args.intake_zip, geometry_report=args.geometry_report)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"s9_omitted_band_count": report["s9_omitted_band_count"],
        "s9_chromatic_body_pixels_in_omitted_bands": report["s9_chromatic_body_pixels_in_omitted_bands"]}))


if __name__ == "__main__":
    main()
