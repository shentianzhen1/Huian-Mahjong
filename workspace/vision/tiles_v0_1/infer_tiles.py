"""Run offline template inference on one screenshot and emit JSON only."""
import argparse
import json
from pathlib import Path

from PIL import Image

from .postprocess import ObservationConstraints, validate_observation
from .roi import ROIProfile
from .template_classifier import TemplateTileClassifier, _tile_face_box


def infer_screenshot(image_path, dataset_root, profile_path, constraints=ObservationConstraints()):
    profile = ROIProfile.load(profile_path)
    if not profile.calibrated:
        raise ValueError("ROI profile must be calibrated from this game-window geometry")
    classifier = TemplateTileClassifier.from_dataset(dataset_root)
    with Image.open(image_path) as source:
        image = source.convert("RGB")
    if image.size != profile.source_size:
        raise ValueError(f"ROI profile requires {profile.source_size}, got {image.size}")
    predictions = []
    markers = []
    for region in profile.regions:
        if profile.region_mode(region) == "marker":
            region_image = profile.crop(image, region)
            x0, y0, _, _ = profile.regions[region]
            slots = profile.slots.get(region) or (
                (0, 0, region_image.width, region_image.height),
            )
            for slot, (x, y, width, height) in enumerate(slots):
                crop = region_image.crop((x, y, x + width, y + height))
                markers.append({
                    "region": region,
                    "slot": slot,
                    "present": _tile_face_box(crop) is not None,
                    "bbox": (x0 + x, y0 + y, width, height),
                })
            continue
        predictions.extend(classifier.classify_slots(image, profile, region))
    result = validate_observation(predictions, constraints)
    return {
        "image": str(Path(image_path)), "profile": profile.name,
        "valid": not result.issues and not result.rejected,
        "predictions": [item.__dict__ for item in result.accepted],
        "rejected_low_confidence": [item.__dict__ for item in result.rejected],
        "issues": list(result.issues),
        "markers": markers,
        "safe_for_executor": False,
    }


def main():
    parser = argparse.ArgumentParser(description="Offline Huian Vision V0.1 tile prototype")
    parser.add_argument("image")
    parser.add_argument("--dataset", default="dataset/tiles_v0_1")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--confidence", type=float, default=.80)
    parser.add_argument("--expected-hand-count", type=int)
    args = parser.parse_args()
    constraints = ObservationConstraints(
        confidence_threshold=args.confidence,
        expected_hand_count=args.expected_hand_count,
    )
    print(json.dumps(
        infer_screenshot(args.image, args.dataset, args.profile, constraints),
        ensure_ascii=False, indent=2,
    ))


if __name__ == "__main__":
    main()
