"""Mine low-motion, continuously visible tile sequences from real recordings."""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .evaluate_stability import temporal_report_to_dict
from .postprocess import TilePrediction, evaluate_temporal_stability
from .roi import ROIProfile
from .template_classifier import (
    TemplateTileClassifier, _feature, _tile_face_box
)


def _feature_similarity(left, right):
    score = float(cv2.matchTemplate(
        left, right, cv2.TM_CCOEFF_NORMED
    )[0, 0])
    return score if np.isfinite(score) else -1.0


def mine_presence_sequences(
        source, dataset_root, profile_path, *,
        region="draw_region", interval_seconds=0.20,
        minimum_frames=3, minimum_similarity=0.85,
        minimum_agreement=0.80):
    """Return continuous visible/low-motion sequences for one tile ROI.

    A sequence ends when the slot becomes empty or the normalized visual feature
    changes below minimum_similarity. Segmentation uses image similarity rather
    than predicted tile_id so the later stability score is not circularly
    defined by its own classifier output.
    """
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive")
    if minimum_frames <= 0:
        raise ValueError("minimum_frames must be positive")
    if not 0 <= minimum_similarity <= 1:
        raise ValueError("minimum_similarity must be between 0 and 1")

    source = Path(source)
    profile = ROIProfile.load(profile_path)
    if not profile.calibrated:
        raise ValueError("ROI profile must be calibrated")
    if profile.region_mode(region) != "tile":
        raise ValueError(f"{region} is not a tile-mode region")
    slots = profile.slots.get(region)
    if not slots:
        raise ValueError(f"No calibrated tile slots for {region}")

    classifier = TemplateTileClassifier.from_dataset(dataset_root)
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise ValueError(f"Cannot open video: {source}")

    fps = capture.get(cv2.CAP_PROP_FPS) or 1.0
    next_seconds = 0.0
    frame_index = 0
    active = {}
    completed = []

    def finish(slot):
        sequence = active.pop(slot, None)
        if sequence and len(sequence["frames"]) >= minimum_frames:
            frames = [
                tuple(TilePrediction(**item) for item in row["predictions"])
                for row in sequence["frames"]
            ]
            stability = evaluate_temporal_stability(
                frames,
                minimum_agreement=minimum_agreement,
                minimum_frames=minimum_frames,
            )
            sequence.pop("last_feature", None)
            sequence["stability"] = temporal_report_to_dict(stability)
            completed.append(sequence)

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            seconds = frame_index / fps
            if seconds + 1e-9 < next_seconds:
                frame_index += 1
                continue

            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if image.size != profile.source_size:
                raise ValueError(
                    f"ROI profile requires {profile.source_size}, got {image.size}"
                )
            rx, ry, _, _ = profile.regions[region]
            region_image = profile.crop(image, region)

            for slot, (x, y, width, height) in enumerate(slots):
                crop = region_image.crop((x, y, x + width, y + height))
                if _tile_face_box(crop) is None:
                    finish(slot)
                    continue

                visual = _feature(crop)
                sequence = active.get(slot)
                if sequence is not None:
                    similarity = _feature_similarity(
                        sequence["last_feature"], visual
                    )
                    if similarity < minimum_similarity:
                        finish(slot)
                        sequence = None
                else:
                    similarity = None

                if sequence is None:
                    sequence = {
                        "slot": slot,
                        "start_seconds": seconds,
                        "end_seconds": seconds,
                        "frames": [],
                        "min_adjacent_similarity": 1.0,
                        "last_feature": visual,
                    }
                    active[slot] = sequence
                elif similarity is not None:
                    sequence["min_adjacent_similarity"] = min(
                        sequence["min_adjacent_similarity"], similarity
                    )
                    sequence["last_feature"] = visual

                prediction = classifier.classify(crop)
                sequence["end_seconds"] = seconds
                sequence["frames"].append({
                    "video_seconds": seconds,
                    "source_frame": frame_index,
                    "predictions": [{
                        "tile_id": prediction.tile_id,
                        "confidence": prediction.confidence,
                        "region": region,
                        "bbox": (rx + x, ry + y, width, height),
                        "slot": slot,
                    }],
                })

            next_seconds += interval_seconds
            frame_index += 1
    finally:
        capture.release()

    for slot in list(active):
        finish(slot)

    stable = sum(
        bool(item["stability"]["stable_slots"]) for item in completed
    )
    return {
        "source": str(source),
        "region": region,
        "interval_seconds": interval_seconds,
        "minimum_frames": minimum_frames,
        "minimum_similarity": minimum_similarity,
        "minimum_agreement": minimum_agreement,
        "sequence_count": len(completed),
        "stable_sequence_count": stable,
        "stable_sequence_fraction": (
            stable / len(completed) if completed else 0.0
        ),
        "sequences": completed,
        "safe_for_executor": False,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Mine continuously visible tile sequences from a recording")
    parser.add_argument("source")
    parser.add_argument("--dataset", default="dataset/tiles_v0_1")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--region", default="draw_region")
    parser.add_argument("--interval", type=float, default=0.20)
    parser.add_argument("--minimum-frames", type=int, default=3)
    parser.add_argument("--minimum-similarity", type=float, default=0.85)
    parser.add_argument("--minimum-agreement", type=float, default=0.80)
    parser.add_argument("--output")
    args = parser.parse_args()

    report = mine_presence_sequences(
        args.source, args.dataset, args.profile,
        region=args.region,
        interval_seconds=args.interval,
        minimum_frames=args.minimum_frames,
        minimum_similarity=args.minimum_similarity,
        minimum_agreement=args.minimum_agreement,
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
