"""Interactive local calibration for one reviewed window size and skin."""
import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .roi import REGION_NAMES, ROIProfile


def _choose_boxes(image, title):
    array = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
    boxes = cv2.selectROIs(title, array, showCrosshair=True, fromCenter=False)
    cv2.destroyWindow(title)
    return tuple(tuple(int(value) for value in box) for box in boxes)


def calibrate(image_path, output_path, slots=False):
    with Image.open(image_path) as source:
        image = source.convert("RGB")
    regions = {}
    for region in REGION_NAMES:
        selected = _choose_boxes(image, f"Select exactly one: {region}")
        if len(selected) != 1:
            raise ValueError(f"Select exactly one rectangle for {region}")
        regions[region] = selected[0]
    profile_slots = {}
    if slots:
        for region, (x, y, width, height) in regions.items():
            crop = image.crop((x, y, x + width, y + height))
            profile_slots[region] = _choose_boxes(crop, f"Select tile slots: {region}")
    profile = ROIProfile(image.size, regions, profile_slots, calibrated=True,
                         name=Path(output_path).stem)
    profile.save(output_path)
    return profile


def main():
    parser = argparse.ArgumentParser(description="Calibrate fixed Vision V0.1 ROIs from a real screenshot")
    parser.add_argument("image")
    parser.add_argument("--output", required=True)
    parser.add_argument("--slots", action="store_true",
                        help="Also select tile slots inside each ROI")
    args = parser.parse_args()
    calibrate(args.image, args.output, args.slots)
    print(f"Saved calibrated ROI profile: {args.output}")


if __name__ == "__main__":
    main()
