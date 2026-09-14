"""Run offline template inference on one screenshot and emit JSON only."""
import argparse
import json
from pathlib import Path

from PIL import Image

from .postprocess import ObservationConstraints, validate_observation
from .roi import ROIProfile
from .template_classifier import TemplateTileClassifier


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
    for region in profile.regions:
        predictions.extend(classifier.classify_slots(image, profile, region))
    result = validate_observation(predictions, constraints)
    return {
        "image": str(Path(image_path)), "profile": profile.name,
        "valid": not result.issues and not result.rejected,
        "predictions": [item.__dict__ for item in result.accepted],
        "rejected_low_confidence": [item.__dict__ for item in result.rejected],
        "issues": list(result.issues),
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
