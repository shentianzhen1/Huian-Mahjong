"""Crop calibrated hand, draw, and gold regions from extracted frames."""
import argparse
import json
from pathlib import Path

from PIL import Image

from .roi import ROIProfile


def _image_paths(dataset_root):
    return sorted((Path(dataset_root) / "images" / "frames").glob("*.png"))


def crop_regions(dataset_root, profile_path, images=None):
    dataset_root = Path(dataset_root)
    profile = ROIProfile.load(profile_path)
    if not profile.calibrated:
        raise ValueError("Refusing to crop with an uncalibrated ROI profile")
    output = dataset_root / "images" / "rois"
    output.mkdir(parents=True, exist_ok=True)
    metadata_path = dataset_root / "meta" / "roi_crops.jsonl"
    rows = []
    with metadata_path.open("a", encoding="utf-8") as stream:
        for image_path in images or _image_paths(dataset_root):
            image_path = Path(image_path)
            with Image.open(image_path) as source:
                image = source.convert("RGB")
            for region in profile.regions:
                crop = profile.crop(image, region)
                filename = f"{image_path.stem}__{region}.png"
                target = output / filename
                crop.save(target)
                row = {
                    "image": str(target.relative_to(dataset_root)).replace("\\", "/"),
                    "source_image": str(image_path.relative_to(dataset_root)).replace("\\", "/"),
                    "region": region, "profile": profile.name,
                    "source_size": list(image.size), "size": list(crop.size),
                    "box": list(profile.regions[region]),
                }
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description="Crop calibrated Huian Vision V0.1 regions")
    parser.add_argument("--dataset", default="dataset/tiles_v0_1")
    parser.add_argument("--profile", required=True)
    parser.add_argument("images", nargs="*")
    args = parser.parse_args()
    rows = crop_regions(args.dataset, args.profile, args.images or None)
    print(f"Wrote {len(rows)} ROI crops")


if __name__ == "__main__":
    main()
