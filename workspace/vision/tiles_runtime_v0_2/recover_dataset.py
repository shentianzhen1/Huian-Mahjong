"""Build a local, review-first inventory from existing Huian replay material.

This module never alters source media, creates no labels or templates, and
never declares a frame to be a playable state.  Its automatic quality filters
only prioritize frames for human review; ROI calibration and tile labels remain
explicit manual actions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from PIL import Image, ImageDraw


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
VIDEO_SUFFIXES = {".avi", ".mp4", ".mov", ".mkv"}
LABEL_FIELDS = (
    "source_id", "source_session", "source_frame", "bbox", "slot", "tile_id",
    "approved", "sha256",
)


@dataclass(frozen=True)
class Sample:
    source: Path
    session: str
    frame: int | None
    seconds: float | None
    size: tuple[int, int]
    sharpness: float
    edge_density: float
    motion: float | None
    preview: np.ndarray


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _session_id(path: Path) -> str:
    return hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:16]


def _measure(frame: np.ndarray, previous: np.ndarray | None) -> tuple[float, float, float | None]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    edges = cv2.Canny(gray, 60, 150)
    edge_density = float(np.count_nonzero(edges) / edges.size)
    small = cv2.resize(gray, (160, 90), interpolation=cv2.INTER_AREA)
    motion = None if previous is None else float(np.mean(cv2.absdiff(small, previous)))
    return sharpness, edge_density, motion


def _image_samples(path: Path) -> Iterable[Sample]:
    frame = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if frame is None:
        return
    sharpness, edge_density, _ = _measure(frame, None)
    yield Sample(path, _session_id(path), None, None, (frame.shape[1], frame.shape[0]),
                 sharpness, edge_density, None, frame)


def _video_samples(path: Path, interval_seconds: float) -> Iterable[Sample]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        return
    fps = capture.get(cv2.CAP_PROP_FPS) or 1.0
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    interval_frames = max(1, int(round(fps * interval_seconds)))
    # Seeking samples avoids decoding every frame of multi-gigabyte AVI files.
    # Motion is deliberately measured only between adjacent sampled timestamps.
    previous = None
    for index in range(0, frame_count, interval_frames):
        capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = capture.read()
        if not ok:
            continue
        sharpness, edge_density, motion = _measure(frame, previous)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        previous = cv2.resize(gray, (160, 90), interpolation=cv2.INTER_AREA)
        yield Sample(path, _session_id(path), index, index / fps,
                     (frame.shape[1], frame.shape[0]), sharpness,
                     edge_density, motion, frame)
    capture.release()


def _sources(roots: Iterable[Path]) -> list[Path]:
    found: set[Path] = set()
    for root in roots:
        if root.exists():
            found.update(path for path in root.rglob("*")
                         if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES | VIDEO_SUFFIXES)
    return sorted(found)


def _relative(path: Path, project_root: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _candidate_rows(samples: list[Sample], project_root: Path) -> tuple[list[dict], dict]:
    by_size: dict[tuple[int, int], list[Sample]] = defaultdict(list)
    for sample in samples:
        by_size[sample.size].append(sample)
    rows, resolution_summary = [], {}
    # A source checksum is traceability metadata, not a per-frame operation.
    # Re-reading a multi-gigabyte replay for every sampled frame is both slow
    # and needlessly stresses the local source disk.
    source_hashes = {sample.source: _sha256(sample.source) for sample in samples}
    for size, group in sorted(by_size.items()):
        sharpness_floor = max(15.0, float(np.quantile([s.sharpness for s in group], 0.35)))
        detail_floor = max(0.005, float(np.quantile([s.edge_density for s in group], 0.20)))
        known_motion = [s.motion for s in group if s.motion is not None]
        motion_ceiling = float(np.quantile(known_motion, 0.75)) if known_motion else None
        accepted = 0
        for sample in group:
            reasons = []
            source_name = sample.source.name.lower()
            # Existing reviewed stills encode known non-play states in their
            # filenames.  This is stronger evidence than a visual heuristic;
            # unlabelled video frames stay review-required rather than guessed.
            if any(token in source_name for token in (
                "settlement", "overview", "winning", "animation", "offer",
            )):
                reasons.append("source_name_indicates_non_play_state")
            if sample.sharpness < sharpness_floor:
                reasons.append("low_sharpness")
            if sample.edge_density < detail_floor:
                reasons.append("low_detail_or_transition")
            if motion_ceiling is not None and sample.motion is not None and sample.motion > motion_ceiling:
                reasons.append("high_transition_motion")
            selected = not reasons
            accepted += int(selected)
            rows.append({
                "source": _relative(sample.source, project_root),
                "source_sha256": source_hashes[sample.source],
                "source_session": sample.session,
                "source_frame": sample.frame,
                "video_seconds": sample.seconds,
                "size": list(sample.size),
                "sharpness": round(sample.sharpness, 3),
                "edge_density": round(sample.edge_density, 5),
                "motion": None if sample.motion is None else round(sample.motion, 3),
                "candidate": selected,
                "automatic_exclusion_reasons": reasons,
                "human_review": "required_for_roi_and_settlement_state",
            })
        resolution_summary[f"{size[0]}x{size[1]}"] = {
            "sampled_frames": len(group), "candidate_frames": accepted,
            "sharpness_floor": round(sharpness_floor, 3),
            "edge_density_floor": round(detail_floor, 5),
            "motion_ceiling": None if motion_ceiling is None else round(motion_ceiling, 3),
        }
    return rows, resolution_summary


def _write_contact_sheets(samples: list[Sample], rows: list[dict], output: Path, maximum: int) -> list[Path]:
    selected = [sample for sample, row in zip(samples, rows) if row["candidate"]]
    by_size: dict[tuple[int, int], list[Sample]] = defaultdict(list)
    for sample in selected:
        by_size[sample.size].append(sample)
    output.mkdir(parents=True, exist_ok=True)
    written = []
    for size, group in sorted(by_size.items()):
        chosen = sorted(group, key=lambda item: item.sharpness, reverse=True)[:maximum]
        if not chosen:
            continue
        thumb_width, thumb_height = 240, 140
        columns = 4
        rows_needed = (len(chosen) + columns - 1) // columns
        sheet = Image.new("RGB", (columns * thumb_width, rows_needed * (thumb_height + 24)), "black")
        draw = ImageDraw.Draw(sheet)
        for index, sample in enumerate(chosen):
            image = Image.fromarray(cv2.cvtColor(sample.preview, cv2.COLOR_BGR2RGB))
            image.thumbnail((thumb_width, thumb_height))
            x = (index % columns) * thumb_width
            y = (index // columns) * (thumb_height + 24)
            sheet.paste(image, (x + (thumb_width - image.width) // 2, y))
            label = f"{sample.source.name}  f={sample.frame if sample.frame is not None else '-'}"
            draw.text((x + 3, y + thumb_height + 3), label[:38], fill="white")
        path = output / f"candidates_{size[0]}x{size[1]}.jpg"
        sheet.save(path, quality=88)
        written.append(path)
    return written


def ensure_layout(dataset: Path) -> None:
    for relative in ("roi_profiles", "templates/hand", "templates/draw", "templates/gold", "validation/generated"):
        (dataset / relative).mkdir(parents=True, exist_ok=True)
    manifest = dataset / "manifest.json"
    if not manifest.exists():
        manifest.write_text(json.dumps({
            "schema_version": "vision_runtime_v0_2",
            "purpose": "reviewed, anonymized runtime asset manifest; no approved runtime assets yet",
            "label_required_fields": list(LABEL_FIELDS),
            "source_reference_policy": "source_id/source_session only; absolute paths are forbidden",
            "privacy": "templates may contain tile crops only; no full frames, player UI, nickname, avatar, or room number",
            "entries": [],
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    labels = dataset / "labels.jsonl"
    labels.touch(exist_ok=True)


def recover(roots: Iterable[Path], dataset: Path, interval_seconds: float, maximum: int,
            project_root: Path) -> dict:
    ensure_layout(dataset)
    samples: list[Sample] = []
    source_counts = Counter()
    for source in _sources(roots):
        iterator = _image_samples(source) if source.suffix.lower() in IMAGE_SUFFIXES else _video_samples(source, interval_seconds)
        for sample in iterator:
            samples.append(sample)
            source_counts[source.suffix.lower()] += 1
    rows, resolutions = _candidate_rows(samples, project_root)
    generated = dataset / "validation" / "generated"
    sheets = _write_contact_sheets(samples, rows, generated, maximum)
    index = dataset / "validation" / "candidate_frames.jsonl"
    index.parent.mkdir(parents=True, exist_ok=True)
    with index.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    report = {
        "schema_version": "vision_runtime_v0_2_recovery_scan",
        "sample_interval_seconds": interval_seconds,
        "source_roots": [_relative(root, project_root) for root in roots],
        "sampled_frames": len(samples),
        "candidate_frames": sum(1 for row in rows if row["candidate"]),
        "sampled_by_type": dict(source_counts),
        "resolutions": resolutions,
        "contact_sheets": [_relative(path, project_root) for path in sheets],
        "human_review_required": True,
        "safe_for_executor": False,
    }
    (dataset / "validation" / "recovery_scan.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Local-only Vision Dataset Recovery V0.2 scan")
    parser.add_argument("--dataset", default="dataset/tiles_runtime_v0_2")
    parser.add_argument("--root", action="append",
                        help="Source root; may be repeated")
    parser.add_argument("--interval", type=float, default=3.0)
    parser.add_argument("--maximum-per-resolution", type=int, default=48)
    args = parser.parse_args()
    if args.interval <= 0 or args.maximum_per_resolution <= 0:
        raise ValueError("interval and maximum-per-resolution must be positive")
    project_root = Path.cwd()
    roots = args.root or ["data/capture_validation", "references"]
    report = recover([Path(root) for root in roots], Path(args.dataset), args.interval,
                     args.maximum_per_resolution, project_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
