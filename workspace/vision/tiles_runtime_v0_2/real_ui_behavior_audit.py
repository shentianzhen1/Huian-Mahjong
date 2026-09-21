"""Mine short real-UI transition windows for manual behavior auditing.

This is an evidence-mining tool, not an Event Tracker.  Heuristic labels are
explicitly candidates and never become gameplay events without human review.
Raw frames and contact sheets stay under the ignored dataset ``work`` tree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from ..capture_validator.auto_recorder import HandPhase, TemplatePhaseDetector
from .dynamic_geometry import detect_dynamic_geometry


VIDEO_SUFFIXES = {".avi", ".mp4", ".mov", ".mkv"}
SAMPLE_FPS = 4.0
WINDOW_SECONDS = 1.5


@dataclass(frozen=True)
class MotionSample:
    frame: int
    seconds: float
    global_diff: float
    bottom_diff: float
    centre_diff: float
    right_diff: float

    @property
    def score(self) -> float:
        return (
            self.global_diff * 0.40
            + self.bottom_diff * 0.35
            + self.centre_diff * 0.15
            + self.right_diff * 0.10
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _motion_samples(path: Path) -> tuple[list[MotionSample], dict]:
    capture = cv2.VideoCapture(str(path))
    fps = float(capture.get(cv2.CAP_PROP_FPS)) or 10.0
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    stride = max(1, int(round(fps / SAMPLE_FPS)))
    previous = None
    samples: list[MotionSample] = []
    frame_number = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if frame_number % stride:
            frame_number += 1
            continue
        gray = cv2.cvtColor(cv2.resize(frame, (192, 108)), cv2.COLOR_BGR2GRAY).astype(np.float32)
        if previous is not None:
            delta = np.abs(gray - previous)
            samples.append(MotionSample(
                frame=frame_number,
                seconds=frame_number / fps,
                global_diff=float(delta.mean()),
                bottom_diff=float(delta[78:108, :].mean()),
                centre_diff=float(delta[28:82, 32:160].mean()),
                right_diff=float(delta[30:96, 150:192].mean()),
            ))
        previous = gray
        frame_number += 1
    capture.release()
    return samples, {
        "fps": fps,
        "frame_count": frame_count,
        "size": [width, height],
        "duration_seconds": frame_count / fps if fps else 0.0,
    }


def _select_peaks(samples: list[MotionSample], fps: float, limit: int) -> list[MotionSample]:
    if not samples:
        return []
    scores = np.asarray([sample.score for sample in samples])
    threshold = max(1.5, float(np.quantile(scores, 0.82)))
    eligible = [sample for sample in samples if sample.score >= threshold]
    selected: list[MotionSample] = []
    minimum_gap = fps * 1.25
    for sample in sorted(eligible, key=lambda item: item.score, reverse=True):
        if all(abs(sample.frame - kept.frame) >= minimum_gap for kept in selected):
            selected.append(sample)
        if len(selected) >= limit:
            break
    return sorted(selected, key=lambda item: item.frame)


def _read_frame(path: Path, frame_number: int) -> Image.Image:
    capture = cv2.VideoCapture(str(path))
    capture.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_number))
    ok, frame = capture.read()
    capture.release()
    if not ok:
        raise ValueError("Could not read an audit candidate frame")
    return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))


def _geometry_signature(image: Image.Image, frame: int, session: str) -> dict:
    observation = detect_dynamic_geometry(image, frame=frame, session=session)
    counts = Counter(component.region_candidate for component in observation.components)
    hand_boxes = [component.pixel_bbox for component in observation.components if component.region_candidate == "hand"]
    baselines = [box[1] + box[3] for box in hand_boxes]
    raised = 0
    if baselines:
        normal = float(np.median(baselines))
        raised = sum(normal - baseline > image.height * 0.025 for baseline in baselines)
    return {
        "counts": dict(counts),
        "geometry_untrusted": observation.geometry_untrusted,
        "issues": list(observation.issues),
        "raised_hand_candidates": raised,
    }


def _button_activity(image: Image.Image) -> float:
    array = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2HSV)
    height, width = array.shape[:2]
    roi = array[int(height * 0.45):int(height * 0.88), int(width * 0.68):width]
    saturation = roi[:, :, 1]
    value = roi[:, :, 2]
    return float(((saturation > 110) & (value > 120)).mean())


def _candidate_types(before: dict, peak: dict, after: dict, sample: MotionSample,
                     phase: str | None, button_delta: float) -> list[str]:
    kinds: list[str] = []
    before_counts, after_counts = before["counts"], after["counts"]
    for region in ("hand", "draw_visual", "meld", "gold"):
        delta = after_counts.get(region, 0) - before_counts.get(region, 0)
        if delta:
            kinds.append(f"{region}_count_{'increase' if delta > 0 else 'decrease'}")
    if before_counts.get("draw_visual", 0) == 0 and peak["counts"].get("draw_visual", 0):
        kinds.append("right_independent_tile_appeared")
    if before_counts.get("draw_visual", 0) and after_counts.get("draw_visual", 0) == 0:
        kinds.append("right_independent_tile_disappeared")
    if max(before["raised_hand_candidates"], peak["raised_hand_candidates"], after["raised_hand_candidates"]):
        kinds.append("single_tile_vertical_motion_candidate")
    if sample.bottom_diff >= sample.centre_diff * 1.15:
        kinds.append("bottom_layout_motion")
    if sample.centre_diff >= sample.bottom_diff * 0.85:
        kinds.append("centre_discard_or_action_motion")
    if button_delta > 0.015 or sample.right_diff > sample.global_diff * 1.25:
        kinds.append("action_button_or_right_ui_change")
    if phase == HandPhase.SETTLEMENT.value:
        kinds.append("settlement_template_candidate")
    if sample.global_diff > 18:
        kinds.append("large_scene_or_overlay_transition")
    return sorted(set(kinds or ["unclassified_visual_transition"]))


def _contact_sheet(frames: list[Image.Image], labels: list[str], output: Path) -> None:
    thumb_width, thumb_height = 240, 150
    sheet = Image.new("RGB", (thumb_width * len(frames), thumb_height + 24), "white")
    for index, (frame, label) in enumerate(zip(frames, labels)):
        thumb = frame.copy()
        thumb.thumbnail((thumb_width, thumb_height))
        x = index * thumb_width + (thumb_width - thumb.width) // 2
        sheet.paste(thumb, (x, 24))
        cv = cv2.cvtColor(np.asarray(sheet), cv2.COLOR_RGB2BGR)
        cv2.putText(cv, label, (index * thumb_width + 4, 17), cv2.FONT_HERSHEY_SIMPLEX,
                    0.42, (0, 0, 0), 1, cv2.LINE_AA)
        sheet = Image.fromarray(cv2.cvtColor(cv, cv2.COLOR_BGR2RGB))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=88)


def mine(root: Path, dataset: Path) -> dict:
    videos = sorted(
        (path for path in root.rglob("*") if path.suffix.lower() in VIDEO_SUFFIXES),
        key=lambda path: path.stat().st_size,
        reverse=True,
    )
    full_game_paths = set(videos[:8])
    work = dataset / "work" / "real_ui_behavior_audit_v0_1"
    manifest_path = work / "candidate_windows.jsonl"
    project_root = Path.cwd()
    phase_detector = TemplatePhaseDetector.from_project_evidence(project_root, threshold=0.90)
    rows: list[dict] = []
    source_summaries: list[dict] = []
    hypothesis_counts: Counter[str] = Counter()
    resolution_counts: Counter[str] = Counter()

    for path in videos:
        source_hash = _sha256(path)
        source_id = "src_" + source_hash[:16]
        session = "session_" + source_hash[:16]
        samples, metadata = _motion_samples(path)
        full_game = path in full_game_paths
        peaks = _select_peaks(samples, metadata["fps"], 14 if full_game else 6)
        resolution_counts[f"{metadata['size'][0]}x{metadata['size'][1]}"] += 1
        source_summaries.append({
            "source_id": source_id,
            "source_session": session,
            "full_game_set": full_game,
            "size": metadata["size"],
            "duration_seconds": round(metadata["duration_seconds"], 3),
            "candidate_windows": len(peaks),
        })
        for peak in peaks:
            radius = int(round(metadata["fps"] * WINDOW_SECONDS))
            frame_numbers = [
                max(0, min(metadata["frame_count"] - 1, peak.frame + int(radius * factor)))
                for factor in (-1.0, -0.5, 0.0, 0.5, 1.0)
            ]
            frames = [_read_frame(path, number) for number in frame_numbers]
            before = _geometry_signature(frames[0], frame_numbers[0], session)
            middle = _geometry_signature(frames[2], frame_numbers[2], session)
            after = _geometry_signature(frames[-1], frame_numbers[-1], session)
            phase = phase_detector.detect(frames[2]).phase
            button_values = [_button_activity(frame) for frame in frames]
            kinds = _candidate_types(
                before, middle, after, peak, phase,
                max(button_values) - min(button_values),
            )
            hypothesis_counts.update(kinds)
            candidate_id = f"ui_audit_{len(rows) + 1:04d}"
            sheet_relative = Path("contact_sheets") / session / f"{candidate_id}.jpg"
            _contact_sheet(
                frames,
                [f"{number} / {number / metadata['fps']:.2f}s" for number in frame_numbers],
                work / sheet_relative,
            )
            rows.append({
                "id": candidate_id,
                "source_id": source_id,
                "source_session": session,
                "source_sha256": source_hash,
                "relative_source_path": path.resolve().relative_to(project_root.resolve()).as_posix(),
                "full_game_set": full_game,
                "size": metadata["size"],
                "fps": metadata["fps"],
                "frame_range": [frame_numbers[0], frame_numbers[-1]],
                "peak_frame": peak.frame,
                "peak_seconds": round(peak.seconds, 3),
                "motion": {
                    "global": round(peak.global_diff, 3),
                    "bottom": round(peak.bottom_diff, 3),
                    "centre": round(peak.centre_diff, 3),
                    "right_ui": round(peak.right_diff, 3),
                },
                "before_geometry": before,
                "peak_geometry": middle,
                "after_geometry": after,
                "phase_template_candidate": phase,
                "button_activity_range": round(max(button_values) - min(button_values), 6),
                "candidate_types": kinds,
                "contact_sheet": sheet_relative.as_posix(),
                "human_review_status": "required",
            })

    work.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    summary = {
        "schema_version": "real_ui_behavior_audit_candidates_v0_1",
        "status": "automatic_candidates_ready_for_human_evidence_review",
        "method": (
            "All local recordings were scanned sequentially at 4 samples/second. "
            "Adaptive frame-difference peaks define +/-1.5 second windows. "
            "Candidate labels are hypotheses, never confirmed events."
        ),
        "sources_scanned": len(videos),
        "full_game_sources": len(full_game_paths),
        "candidate_windows": len(rows),
        "resolution_source_counts": dict(resolution_counts),
        "candidate_type_counts": dict(hypothesis_counts.most_common()),
        "sources": source_summaries,
        "private_work_manifest": "work/real_ui_behavior_audit_v0_1/candidate_windows.jsonl",
        "private_contact_sheets": "work/real_ui_behavior_audit_v0_1/contact_sheets/",
        "privacy": "Full frames and local filenames remain ignored local work products.",
        "safe_for_executor": False,
    }
    report = dataset / "validation" / "reports" / "real_ui_behavior_audit_candidate_summary_v0_1.json"
    report.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="data/capture_validation")
    parser.add_argument("--dataset", default="dataset/tiles_runtime_v0_2")
    args = parser.parse_args()
    print(json.dumps(mine(Path(args.root), Path(args.dataset)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
