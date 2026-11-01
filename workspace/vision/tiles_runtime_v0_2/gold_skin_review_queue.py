"""Local-only review queue for real yellow Gold-skinned concealed tiles.

This tool is intentionally non-authoritative. It scans a private local video,
finds Gold-skinned hand/draw components with the existing dynamic geometry,
ranks each crop with the current Gold-normalized classifier, and writes a
PRIVATE review queue outside the Git repository.

It never edits labels.jsonl, never marks a crop approved, and never makes a
runtime promotion decision.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

import cv2
from PIL import Image

from workspace.vision.tiles_v0_1.labels import approved_labels
from workspace.vision.tiles_v0_1.template_classifier import TemplateTileClassifier

from .dynamic_geometry import detect_dynamic_geometry
from .runtime_reader import _training_labels
from .tile_crop import classification_crop_bbox


SESSION_RE = re.compile(r"^[A-Za-z0-9_.-]{3,96}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_root(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _validate_private_output(output_dir: Path, *, working_dir: Path | None = None) -> None:
    root = _git_root(working_dir or Path.cwd())
    if root is not None and _is_within(output_dir, root):
        raise ValueError(
            "output_dir must be outside the Git repository; private crops must not be committed"
        )


@dataclass(frozen=True)
class GoldReviewCandidate:
    frame_id: int
    seconds: float
    region: str
    geometry_bbox: tuple[int, int, int, int]
    crop_bbox: tuple[int, int, int, int]
    candidate_tile_id: str
    confidence: float
    crop: Image.Image

    def metadata(self) -> dict:
        return {
            "frame_id": self.frame_id,
            "seconds": round(self.seconds, 3),
            "region": self.region,
            "geometry_bbox": list(self.geometry_bbox),
            "crop_bbox": list(self.crop_bbox),
            "candidate_tile_id": self.candidate_tile_id,
            "confidence": round(self.confidence, 6),
            "status": "proposed",
            "approved": False,
            "review_required": True,
            "safe_for_hint": False,
            "safe_for_executor": False,
        }


def propose_gold_skin_candidates(
    image: Image.Image,
    classifier: TemplateTileClassifier,
    *,
    frame_id: int,
    seconds: float,
    source_session: str,
) -> list[GoldReviewCandidate]:
    """Return yellow concealed candidates from one frame without approving them."""
    geometry = detect_dynamic_geometry(
        image,
        frame=frame_id,
        session=source_session,
    )
    all_boxes = [component.pixel_bbox for component in geometry.components]
    proposed: list[GoldReviewCandidate] = []
    for component in geometry.components:
        if not component.gold_skin:
            continue
        if component.region_candidate not in {"hand", "draw_visual"}:
            continue
        crop_bbox = classification_crop_bbox(
            component.pixel_bbox,
            frame_size=image.size,
            neighbors=[box for box in all_boxes if box != component.pixel_bbox],
        )
        x, y, width, height = crop_bbox
        crop = image.crop((x, y, x + width, y + height))
        prediction = classifier.classify_gold_skin(crop)
        proposed.append(
            GoldReviewCandidate(
                frame_id=frame_id,
                seconds=seconds,
                region=(
                    "hand_region"
                    if component.region_candidate == "hand"
                    else "draw_visual"
                ),
                geometry_bbox=component.pixel_bbox,
                crop_bbox=crop_bbox,
                candidate_tile_id=prediction.tile_id,
                confidence=prediction.confidence,
                crop=crop,
            )
        )
    return proposed


def _dedupe_candidates(
    candidates: list[GoldReviewCandidate],
    *,
    frame_width: int,
) -> list[GoldReviewCandidate]:
    """Keep the clearest crop per approximate physical slot and top-1 class."""
    best: dict[tuple[str, int, str], GoldReviewCandidate] = {}
    for candidate in candidates:
        x, _, width, _ = candidate.crop_bbox
        centre_x = x + width / 2
        slot_bucket = int(round((centre_x / max(frame_width, 1)) * 50))
        key = (candidate.region, slot_bucket, candidate.candidate_tile_id)
        current = best.get(key)
        if current is None or candidate.confidence > current.confidence:
            best[key] = candidate
    return list(best.values())


def build_gold_skin_review_queue(
    source: str | Path,
    dataset_root: str | Path,
    output_dir: str | Path,
    *,
    source_session: str,
    start_seconds: float,
    end_seconds: float,
    sample_fps: float = 2.0,
    target_tile: str | None = "M6",
    max_candidates: int = 12,
) -> dict:
    """Scan a private local video and write a non-authoritative crop queue."""
    if not SESSION_RE.fullmatch(source_session):
        raise ValueError("source_session must be an anonymized 3-96 character identifier")
    if start_seconds < 0 or end_seconds <= start_seconds:
        raise ValueError("end_seconds must be greater than start_seconds >= 0")
    if sample_fps <= 0:
        raise ValueError("sample_fps must be positive")
    if max_candidates < 1:
        raise ValueError("max_candidates must be positive")

    source = Path(source)
    dataset = Path(dataset_root)
    output = Path(output_dir)
    if not source.is_file():
        raise ValueError("source must be an existing private video file")
    _validate_private_output(output)

    source_sha = _sha256(source)
    source_id = f"src_{source_sha[:16]}"
    labels = approved_labels(dataset)
    training = _training_labels(labels, source_session)
    classifier = TemplateTileClassifier.from_labels(dataset, training)

    capture = cv2.VideoCapture(str(source))
    all_candidates: list[GoldReviewCandidate] = []
    frame_width = 0
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        if not fps or fps <= 0:
            raise ValueError("video FPS is unavailable")
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if frame_count <= 0:
            raise ValueError("video frame count is unavailable")
        frame_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        start_frame = max(0, int(round(start_seconds * fps)))
        end_frame = min(frame_count - 1, int(round(end_seconds * fps)))
        step = max(1, int(round(fps / sample_fps)))
        for frame_id in range(start_frame, end_frame + 1, step):
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
            ok, frame = capture.read()
            if not ok:
                continue
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            all_candidates.extend(
                propose_gold_skin_candidates(
                    image,
                    classifier,
                    frame_id=frame_id,
                    seconds=frame_id / fps,
                    source_session=source_session,
                )
            )
    finally:
        capture.release()

    unique = _dedupe_candidates(all_candidates, frame_width=frame_width)
    unique.sort(
        key=lambda candidate: (
            0 if target_tile and candidate.candidate_tile_id == target_tile else 1,
            -candidate.confidence,
            candidate.frame_id,
            candidate.crop_bbox[0],
        )
    )
    selected = unique[:max_candidates]

    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for index, candidate in enumerate(selected, start=1):
        x, y, width, height = candidate.crop_bbox
        name = (
            f"{index:02d}_{source_id}_f{candidate.frame_id}_"
            f"x{x}_y{y}_w{width}_h{height}_"
            f"{candidate.candidate_tile_id}_{candidate.confidence:.4f}.png"
        )
        asset = output / name
        candidate.crop.save(asset, format="PNG")
        row = candidate.metadata()
        row.update({
            "private_crop_file": name,
            "private_crop_sha256": _sha256(asset),
        })
        rows.append(row)

    report = {
        "schema_version": "gold_skin_private_review_queue_v0_1",
        "source_id": source_id,
        "source_sha256": source_sha,
        "source_session": source_session,
        "start_seconds": start_seconds,
        "end_seconds": end_seconds,
        "sample_fps": sample_fps,
        "target_tile": target_tile,
        "total_gold_skin_detections": len(all_candidates),
        "deduped_candidates": len(unique),
        "exported_candidates": len(rows),
        "approved_labels_written": 0,
        "requires_manual_source_frame_review": True,
        "safe_for_hint": False,
        "safe_for_executor": False,
        "candidates": rows,
    }
    (output / "review_queue.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a private review queue for yellow Gold-skinned concealed tiles"
    )
    parser.add_argument("--video", required=True)
    parser.add_argument("--dataset", default="dataset/tiles_runtime_v0_2")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--source-session", required=True)
    parser.add_argument("--start-seconds", type=float, required=True)
    parser.add_argument("--end-seconds", type=float, required=True)
    parser.add_argument("--sample-fps", type=float, default=2.0)
    parser.add_argument("--target-tile", default="M6")
    parser.add_argument("--max-candidates", type=int, default=12)
    args = parser.parse_args()
    report = build_gold_skin_review_queue(
        args.video,
        args.dataset,
        args.output_dir,
        source_session=args.source_session,
        start_seconds=args.start_seconds,
        end_seconds=args.end_seconds,
        sample_fps=args.sample_fps,
        target_tile=args.target_tile,
        max_candidates=args.max_candidates,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
