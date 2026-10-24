"""Verify pinned Hand 8 crop pixels against exact source video frames via FFmpeg."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
from zipfile import ZipFile


def evaluate(*, video_path: str | Path, intake_zip: str | Path,
             pinned_ledger_path: str | Path = "references/vision/2026-10-03/hand8_s789_intake_v0_1.json") -> dict:
    from PIL import Image

    video_path, intake_zip, pinned_ledger_path = map(Path, (video_path, intake_zip, pinned_ledger_path))
    pinned = json.loads(pinned_ledger_path.read_text())
    video_sha = hashlib.sha256(video_path.read_bytes()).hexdigest()
    source = pinned["spec"]["sources"][0]
    if video_sha != source["source_sha256"]:
        raise ValueError("source video SHA differs from pinned Hand 8 source")
    expected_frames = pinned["spec"]["sources"][0]["groups"][0]["frame_indices"]
    with ZipFile(intake_zip) as archive:
        intake = json.loads(archive.read("intake.json"))
        if intake != pinned:
            raise ValueError("private intake ledger differs from pinned metadata")
        rows = intake["faces"]
        if len(rows) != 15 or sorted({row["frame_index"] for row in rows}) != expected_frames:
            raise ValueError("expected exactly 15 faces across the five pinned frames")
        with tempfile.TemporaryDirectory(prefix="hand8_ffmpeg_pixels_") as temp:
            pattern = Path(temp) / "frame-%02d.png"
            selection = "+".join(f"eq(n,{frame})" for frame in expected_frames)
            command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(video_path),
                "-vf", f"select='{selection}'", "-vsync", "0", "-start_number", "0", str(pattern), "-y"]
            subprocess.run(command, check=True, capture_output=True, text=True)
            output = []
            for slot, frame in enumerate(expected_frames):
                decoded_path = Path(temp) / f"frame-{slot:02d}.png"
                with Image.open(decoded_path) as decoded:
                    source_image = decoded.convert("RGB")
                for row in sorted((r for r in rows if r["frame_index"] == frame), key=lambda r: r["face_index"]):
                    crop_raw = archive.read(row["crop_file"])
                    if hashlib.sha256(crop_raw).hexdigest() != row["crop_sha256"]:
                        raise ValueError("pinned intake crop SHA mismatch")
                    x, y, width, height = row["bbox"]
                    actual = source_image.crop((x, y, x + width, y + height))
                    with Image.open(io.BytesIO(crop_raw)) as reviewed:
                        reviewed_image = reviewed.convert("RGB")
                    exact = actual.size == reviewed_image.size and actual.tobytes() == reviewed_image.tobytes()
                    if not exact:
                        raise ValueError(f"source pixel mismatch at frame={frame} face={row['face_index']}")
                    output.append({"frame": frame, "face_index": row["face_index"],
                        "crop_sha256": row["crop_sha256"], "source_crop_pixels_exact": True})
    version = subprocess.run(["ffmpeg", "-version"], check=True, capture_output=True, text=True).stdout.splitlines()[0]
    return {"schema_version": "hand8_crop_source_pixel_verification_dev_v0_1",
        "source_video_sha256": video_sha, "ffmpeg_version": version,
        "exact_source_crop_count": len(output), "face_crop_pixels_exact": True,
        "frames": expected_frames, "verified_crops": output,
        "crop_or_source_search_performed": False, "private_raw_video_in_repository": False,
        "formal_identity_truth": False, "identity_rerank_performed": False,
        "runtime_integration": False, "safe_for_runtime": False,
        "safe_for_hint": False, "safe_for_executor": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True)
    parser.add_argument("--intake-zip", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = evaluate(video_path=args.video, intake_zip=args.intake_zip)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"source_video_sha256": report["source_video_sha256"],
        "exact_source_crop_count": report["exact_source_crop_count"],
        "face_crop_pixels_exact": report["face_crop_pixels_exact"]}))


if __name__ == "__main__":
    main()
