"""Read-only, SHA-locked REAL video frame intake for the Roboflow trial.

Use only private paths and a bounded list of reviewed video-relative frames.
This is development diagnostics, not a source-disjoint accuracy experiment.
No video, JPEGs, key, or raw API response is committed to GitHub.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from typing import Any, Callable

from workspace.vision.roboflow_public_eval import (
    API_URL, MODEL_ID, _parse_prediction,
)

_SHA = re.compile(r"^[0-9a-f]{64}$")


def file_sha256(file_path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(file_path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_indices(raw: str) -> list[int]:
    try:
        items = [int(x.strip()) for x in raw.split(",")]
    except (TypeError, ValueError) as exc:
        raise ValueError("frames must be comma-separated nonnegative integers") from exc
    if (not items or len(items) > 48 or any(x < 0 for x in items)
            or len(items) != len(set(items))):
        raise ValueError("use between 1 and 48 UNIQUE nonnegative frame indices")
    return sorted(items)


def normalized_roi(values: str | None) -> tuple[float, float, float, float] | None:
    if values is None:
        return None
    try:
        x, y, w, h = (float(v.strip()) for v in values.split(","))
    except (ValueError, TypeError) as exc:
        raise ValueError("ROI needs x,y,width,height") from exc
    if (not all(math.isfinite(v) for v in (x, y, w, h))
            or x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > 1 or y + h > 1):
        raise ValueError("ROI must be normalized and inside the full frame")
    return x, y, w, h


def trial_video(
    video: str | Path, *, expected_sha256: str, source_group: str,
    frames: list[int], infer: Callable[[str], dict[str, Any]] | None = None,
    roi: tuple[float, float, float, float] | None = None,
    private_frames_dir: str | Path | None = None,
) -> dict[str, Any]:
    import cv2  # optional Vision dependency

    path = Path(video)
    if not path.is_file():
        raise FileNotFoundError("real recording unavailable")
    if not isinstance(expected_sha256, str) or not _SHA.fullmatch(expected_sha256.lower()):
        raise ValueError("exact 64-digit video source SHA256 required")
    actual_sha = file_sha256(path)
    if actual_sha != expected_sha256.lower():
        raise ValueError("video SHA256 mismatch; refusing to sample a different source")
    if not source_group or not source_group.strip():
        raise ValueError("explicit original MATCH group required, not a per-hand group")
    if (not frames or len(frames) > 48 or len(frames) != len(set(frames))
            or any(type(i) is not int or i < 0 for i in frames)):
        raise ValueError("expected 1-48 distinct nonnegative frame indices")

    output_dir = Path(private_frames_dir).resolve() if private_frames_dir else None
    if output_dir is not None:
        repo_root = Path(__file__).resolve().parents[2]
        if output_dir.is_relative_to(repo_root):
            raise ValueError("private frame output must not be inside the public repo")
        output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError("cannot decode source recording")
    try:
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        if (count <= 0 or width <= 0 or height <= 0
                or not math.isfinite(fps) or fps <= 0):
            raise ValueError("missing real video metadata")
        if max(frames) >= count:
            raise ValueError("frame index outside source recording")
        report: dict[str, Any] = {
            "schema_version": "roboflow_video_probe_v0_1",
            "model_id": MODEL_ID,
            "mode": "offline_video_preflight" if infer is None else "cloud_video_inference",
            "source_sha256": actual_sha,
            "source_group": source_group,
            "video_resolution": [width, height],
            "video_frame_count": count,
            "fps": round(fps, 4),
            "sampled_frames": [],
            "model_calls": 0,
            "approved_ground_truth_labels": 0,
            "recognition_accuracy": None,
            "source_disjoint_blind_holdout": False,
            "formal_promotion_evidence": False,
            "runtime_identity_ready": False,
            "safe_for_executor": False,
        }
        unknown: Counter[str] = Counter()
        with TemporaryDirectory(prefix="huian_roboflow_") as temp:
            for index in sorted(frames):
                cap.set(cv2.CAP_PROP_POS_FRAMES, index)
                ok, image = cap.read()
                if not ok or image.shape[:2] != (height, width):
                    raise ValueError("video frame unavailable or wrong resolution")
                left, top, right, bottom = 0, 0, width, height
                if roi is not None:
                    x, y, w, h = roi
                    left, top = round(x * width), round(y * height)
                    right, bottom = round((x + w) * width), round((y + h) * height)
                    if right <= left or bottom <= top:
                        raise ValueError("ROI resolved to empty pixels")
                    image = image[top:bottom, left:right]
                success, payload = cv2.imencode(
                    ".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 95]
                )
                if not success:
                    raise ValueError("cannot JPEG-encode source frame")
                jpg = payload.tobytes()
                basename = f"frame_{index:06d}.jpg"
                if output_dir is not None:
                    (output_dir / basename).write_bytes(jpg)
                row: dict[str, Any] = {
                    "frame": index,
                    "seconds": round(index / fps, 4),
                    "submitted_jpeg_sha256": hashlib.sha256(jpg).hexdigest(),
                    "detections": [],
                }
                if infer is not None:
                    temporary_jpg = Path(temp) / basename
                    temporary_jpg.write_bytes(jpg)
                    response = infer(str(temporary_jpg))
                    if not isinstance(response, dict) or not isinstance(
                            response.get("predictions"), list):
                        raise ValueError("model response lacks predictions array")
                    im_w, im_h = image.shape[1], image.shape[0]
                    dimensions = response.get("image")
                    if isinstance(dimensions, dict) and all(
                            x in dimensions for x in ("width", "height")):
                        if (int(dimensions["width"]), int(dimensions["height"])) != (im_w, im_h):
                            raise ValueError("model response image resolution mismatch")
                    for pred in response["predictions"]:
                        item = _parse_prediction(pred, (im_w, im_h))
                        cx, cy, cw, ch = item["bbox"]
                        item["bbox"] = [
                            round((left + cx * im_w) / width, 6),
                            round((top + cy * im_h) / height, 6),
                            round(cw * im_w / width, 6),
                            round(ch * im_h / height, 6),
                        ]
                        if item["tile_id"] is None:
                            unknown[item["raw_class"]] += 1
                        row["detections"].append(item)
                    report["model_calls"] += 1
                report["sampled_frames"].append(row)
        report["total_detections"] = sum(
            len(item["detections"]) for item in report["sampled_frames"]
        )
        report["unmapped_source_classes"] = dict(sorted(unknown.items()))
        return report
    finally:
        cap.release()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--source-group", required=True)
    parser.add_argument("--frames", required=True)
    parser.add_argument("--roi", default=None)
    parser.add_argument("--output", required=True)
    parser.add_argument("--private-frames-dir", default=None)
    parser.add_argument("--cloud", action="store_true",
                        help="Explicitly authorize uploading selected private JPEGs")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    output = Path(args.output).resolve()
    if output.is_relative_to(root):
        parser.error("private video trial reports must be outside public checkout")
    infer = None
    if args.cloud:
        key = os.environ.get("ROBOFLOW_API_KEY", "")
        if not key.strip():
            parser.error("ROBOFLOW_API_KEY is required for the explicit cloud mode")
        try:
            from inference_sdk import InferenceConfiguration, InferenceHTTPClient
        except ImportError:
            parser.error("install inference-sdk for cloud video testing")
        client = InferenceHTTPClient(api_url=API_URL, api_key=key).configure(
            InferenceConfiguration(api_key_transport="header")
        )
        infer = lambda file_path: client.infer(file_path, model_id=MODEL_ID)
    try:
        result = trial_video(args.video, expected_sha256=args.expected_sha256,
                             source_group=args.source_group,
                             frames=parse_indices(args.frames),
                             infer=infer, roi=normalized_roi(args.roi),
                             private_frames_dir=args.private_frames_dir)
    except Exception as exc:
        if args.cloud:
            parser.exit(2, "Cloud video trial failed (" + type(exc).__name__
                        + "); raw error suppressed to protect credentials.\n")
        raise
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in (
        "mode", "source_group", "model_calls", "total_detections",
        "recognition_accuracy", "safe_for_executor"
    )}))


if __name__ == "__main__":
    main()
