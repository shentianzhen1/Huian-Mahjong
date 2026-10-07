"""Export the frozen Runtime V0.2 template baseline on reviewed whole-hand truth.

Private source video and derived crops stay local. The committed truth seed may
contain only reviewed identities/timestamps and source hashes; this tool joins
that truth with the *current* detector/crop/classifier path and writes an audit
bundle under a caller-provided local output directory.

The 0.82 identity threshold is intentionally hard-coded here. This tool is not
an optimization loop and must not be used to tune the threshold on the reviewed
batch.

Vision-only imports stay inside the execution functions so the repository's
core test matrix can import the pure alignment helpers without installing
OpenCV/Pillow. Running the exporter itself still requires the normal Vision
extras, exactly like Runtime V0.2.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

from .whole_hand_eval import FROZEN_CONFIDENCE_THRESHOLD


TRUTH_SEED_SCHEMA = "vision_whole_hand_truth_seed_v0_1"
EXPORT_SCHEMA = "vision_runtime_v0_2_whole_hand_baseline_export_v0_1"
BURST_SIZE = 5


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_truth_seed(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != TRUTH_SEED_SCHEMA:
        raise ValueError(f"truth seed schema must be {TRUTH_SEED_SCHEMA!r}")
    source = payload.get("source")
    if not isinstance(source, dict):
        raise ValueError("truth seed source must be an object")
    samples = payload.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("truth seed samples must be a non-empty array")
    grouping = payload.get("source_grouping")
    if not isinstance(grouping, dict) or not grouping.get("original_match_group"):
        raise ValueError("truth seed must declare original_match_group")
    return payload


def _read_burst(video_path: Path, seconds: float) -> tuple[list[int], list[Any], dict]:
    import cv2
    from PIL import Image

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"Could not open video: {video_path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if fps <= 0 or frame_count <= 0:
        capture.release()
        raise ValueError("Video metadata does not expose usable fps/frame_count")

    centre = int(round(float(seconds) * fps))
    half = BURST_SIZE // 2
    start = max(0, min(frame_count - BURST_SIZE, centre - half))
    frame_ids = list(range(start, min(frame_count, start + BURST_SIZE)))
    if len(frame_ids) != BURST_SIZE:
        capture.release()
        raise ValueError("Could not form a five-frame burst at requested timestamp")

    capture.set(cv2.CAP_PROP_POS_FRAMES, frame_ids[0])
    images: list[Any] = []
    decoded_ids: list[int] = []
    for frame_id in frame_ids:
        ok, frame = capture.read()
        if not ok:
            capture.release()
            raise ValueError(f"Could not decode frame {frame_id}")
        decoded_ids.append(frame_id)
        images.append(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    capture.release()
    return decoded_ids, images, {
        "fps": fps,
        "frame_count": frame_count,
        "decoded_size": [width, height],
    }


def _component_sort_key(component: dict) -> tuple[int, int, int]:
    x, y, _, _ = component.get("pixel_bbox", [0, 0, 0, 0])
    return int(x), int(y), int(component.get("frame") or 0)


def _save_component_crops(
    sample_dir: Path,
    components: list[dict],
    images_by_frame: dict[int, Any],
) -> list[dict]:
    output: list[dict] = []
    sample_dir.mkdir(parents=True, exist_ok=True)
    region_counts: Counter[str] = Counter()
    for component in components:
        item = dict(component)
        region = str(item.get("region_candidate") or "unknown")
        region_counts[region] += 1
        frame_id = item.get("frame")
        crop_bbox = item.get("classification_crop_bbox")
        if isinstance(frame_id, int) and crop_bbox and frame_id in images_by_frame:
            x, y, width, height = (int(value) for value in crop_bbox)
            crop = images_by_frame[frame_id].crop((x, y, x + width, y + height))
            filename = f"{region}_{region_counts[region]:02d}_frame_{frame_id}.png"
            crop.save(sample_dir / filename)
            item["private_crop_ref"] = filename
        else:
            item["private_crop_ref"] = None
        output.append(item)
    return output


def _truth_counts(sample: dict) -> tuple[int, int]:
    truth = sample.get("truth")
    if not isinstance(truth, dict):
        raise ValueError(f"sample {sample.get('sample_id')!r} has no truth object")
    hand = truth.get("concealed_hand")
    if not isinstance(hand, list):
        raise ValueError(f"sample {sample.get('sample_id')!r} concealed_hand must be an array")
    return len(hand), int(bool(truth.get("draw_visual")))


def _align_exact_counts(sample: dict, components: list[dict]) -> dict:
    """Align by display order only when detector counts exactly match truth.

    A count mismatch deliberately does not guess which truth slot was missed.
    It is surfaced as manual_alignment_required so one missed box cannot shift
    every later tile and masquerade as classifier confusion.
    """
    truth = sample["truth"]
    truth_hand = list(truth["concealed_hand"])
    truth_draw = truth.get("draw_visual")
    hand = sorted(
        (row for row in components if row.get("region_candidate") == "hand"),
        key=_component_sort_key,
    )
    draw = sorted(
        (row for row in components if row.get("region_candidate") == "draw_visual"),
        key=_component_sort_key,
    )
    expected_draw_count = int(bool(truth_draw))
    if len(hand) != len(truth_hand) or len(draw) != expected_draw_count:
        return {
            "status": "manual_alignment_required",
            "truth_hand_count": len(truth_hand),
            "detected_hand_count": len(hand),
            "truth_draw_count": expected_draw_count,
            "detected_draw_count": len(draw),
            "slots": [],
        }

    slots = []
    for index, (truth_tile, observation) in enumerate(zip(truth_hand, hand)):
        slots.append({
            "slot": index,
            "region": "hand",
            "truth_tile": truth_tile,
            "crop_status": "unreviewed",
            "candidate_tile_id": observation.get("candidate_tile_id"),
            "accepted_tile_id": observation.get("tile_id", "UNKNOWN"),
            "confidence": observation.get("tile_confidence", 0.0),
            "identity_reason": observation.get("identity_reason"),
            "pixel_bbox": observation.get("pixel_bbox"),
            "classification_crop_bbox": observation.get("classification_crop_bbox"),
            "private_crop_ref": observation.get("private_crop_ref"),
        })
    if truth_draw:
        observation = draw[0]
        slots.append({
            "slot": len(truth_hand),
            "region": "draw_visual",
            "truth_tile": truth_draw,
            "crop_status": "unreviewed",
            "candidate_tile_id": observation.get("candidate_tile_id"),
            "accepted_tile_id": observation.get("tile_id", "UNKNOWN"),
            "confidence": observation.get("tile_confidence", 0.0),
            "identity_reason": observation.get("identity_reason"),
            "pixel_bbox": observation.get("pixel_bbox"),
            "classification_crop_bbox": observation.get("classification_crop_bbox"),
            "private_crop_ref": observation.get("private_crop_ref"),
        })
    return {
        "status": "exact_count_left_to_right_alignment_pending_crop_review",
        "truth_hand_count": len(truth_hand),
        "detected_hand_count": len(hand),
        "truth_draw_count": expected_draw_count,
        "detected_draw_count": len(draw),
        "slots": slots,
    }


def _sample_summary(alignment: dict, runtime_report: dict) -> dict:
    slots = alignment.get("slots", [])
    return {
        "geometry_untrusted": bool(runtime_report.get("geometry_untrusted")),
        "alignment_status": alignment["status"],
        "accepted_exact_before_crop_review": sum(
            row.get("accepted_tile_id") == row.get("truth_tile") for row in slots
        ),
        "accepted_wrong_before_crop_review": sum(
            row.get("accepted_tile_id") not in {"UNKNOWN", row.get("truth_tile")} for row in slots
        ),
        "rejected_before_crop_review": sum(
            row.get("accepted_tile_id") == "UNKNOWN" for row in slots
        ),
        "crop_review_required": bool(slots),
    }


def export_baseline(
    video_path: Path,
    truth_seed_path: Path,
    dataset_root: Path,
    output_dir: Path,
) -> dict:
    # Keep the Vision dependency boundary lazy. Core CI intentionally does not
    # install OpenCV/Pillow, while this execution path is part of Vision.
    from .runtime_reader import prepare_runtime_resources, read_stable_frames

    seed = _load_truth_seed(truth_seed_path)
    source_hash = _sha256(video_path)
    expected_hash = str(seed["source"].get("sha256") or "").lower()
    if expected_hash and source_hash.lower() != expected_hash:
        raise ValueError(
            "private video SHA-256 does not match the reviewed truth seed; "
            "refusing to score a different source"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    session = "whole_hand_" + source_hash[:16]
    resources = prepare_runtime_resources(dataset_root, session=session)
    geometry_cache = {}
    samples = []
    video_metadata = None

    for sample in seed["samples"]:
        sample_id = str(sample["sample_id"])
        seconds = float(sample["timestamp_seconds"])
        frame_ids, images, metadata = _read_burst(video_path, seconds)
        video_metadata = metadata
        runtime_report = read_stable_frames(
            images,
            dataset_root,
            frame_ids=frame_ids,
            session=session,
            confidence_threshold=FROZEN_CONFIDENCE_THRESHOLD,
            resources=resources,
            geometry_cache=geometry_cache,
        )
        images_by_frame = dict(zip(frame_ids, images))
        components = _save_component_crops(
            output_dir / "crops" / sample_id,
            list(runtime_report.get("components", [])),
            images_by_frame,
        )
        alignment = _align_exact_counts(sample, components)
        truth_hand_count, truth_draw_count = _truth_counts(sample)
        samples.append({
            "sample_id": sample_id,
            "timestamp_seconds": seconds,
            "frame_ids": frame_ids,
            "truth": sample["truth"],
            "truth_counts": {
                "hand": truth_hand_count,
                "draw_visual": truth_draw_count,
            },
            "runtime": {
                key: value
                for key, value in runtime_report.items()
                if key not in {"components"}
            },
            "components": components,
            "alignment": alignment,
            "summary": _sample_summary(alignment, runtime_report),
        })

    status_counts = Counter(row["summary"]["alignment_status"] for row in samples)
    report = {
        "schema_version": EXPORT_SCHEMA,
        "status": "PRIVATE_BASELINE_EXPORT_REQUIRES_CROP_REVIEW",
        "source": {
            "filename": video_path.name,
            "sha256": source_hash,
            "metadata": video_metadata,
        },
        "truth_seed": truth_seed_path.as_posix(),
        "original_match_group": seed["source_grouping"]["original_match_group"],
        "runtime_model": "template_runtime_v0_2",
        "confidence_threshold": FROZEN_CONFIDENCE_THRESHOLD,
        "confidence_threshold_frozen": True,
        "source_session_is_independence_signal": False,
        "adjacent_frames_are_one_original_match_source": True,
        "sample_count": len(samples),
        "alignment_status_counts": dict(sorted(status_counts.items())),
        "samples": samples,
        "privacy": "This report and crops are local/private audit products; do not commit raw or derived frame data.",
        "next_step": (
            "Review every exported crop and mark ok/bad_crop/shadowed/prompt_occlusion; "
            "manually align count-mismatch samples before whole_hand_eval scoring."
        ),
        "safe_for_runtime_change": False,
        "safe_for_hint_promotion": False,
        "safe_for_executor": False,
    }
    report_path = output_dir / "baseline_export.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export frozen Runtime V0.2 whole-hand baseline evidence at reviewed timestamps"
    )
    parser.add_argument("video")
    parser.add_argument("truth_seed")
    parser.add_argument("--dataset", default="dataset/tiles_runtime_v0_2")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = export_baseline(
        Path(args.video),
        Path(args.truth_seed),
        Path(args.dataset),
        Path(args.output),
    )
    print(json.dumps({
        "schema_version": report["schema_version"],
        "sample_count": report["sample_count"],
        "alignment_status_counts": report["alignment_status_counts"],
        "confidence_threshold": report["confidence_threshold"],
        "report": str(Path(args.output) / "baseline_export.json"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
