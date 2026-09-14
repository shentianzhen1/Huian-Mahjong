"""Local manual or suggestion-assisted tile-box annotation."""
import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .labels import append_label
from .taxonomy import TILE_CLASSES
from .template_classifier import TemplateTileClassifier


def annotate(image_path, dataset_root, region, *, suggestions=False):
    root = Path(dataset_root)
    image_path = Path(image_path)
    with Image.open(image_path) as source:
        image = source.convert("RGB")
    display = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
    boxes = cv2.selectROIs("Select tile boxes, then press Enter", display,
                           showCrosshair=True, fromCenter=False)
    cv2.destroyWindow("Select tile boxes, then press Enter")
    classifier = None
    if suggestions:
        try:
            classifier = TemplateTileClassifier.from_dataset(root)
        except ValueError:
            print("No reviewed templates yet; continuing with manual labels.")
    image_ref = str(image_path.resolve().relative_to(root.resolve())).replace("\\", "/")
    rows = []
    for box in boxes:
        x, y, width, height = (int(value) for value in box)
        suggestion = ""
        if classifier:
            suggestion = classifier.classify(image.crop((x, y, x + width, y + height))).tile_id
        prompt = f"Tile class {sorted(TILE_CLASSES)}"
        if suggestion:
            prompt += f" [{suggestion}]"
        tile_id = input(prompt + ": ").strip() or suggestion
        if tile_id not in TILE_CLASSES:
            print(f"Skipped invalid class: {tile_id}")
            continue
        rows.append(append_label(
            root, image=image_ref, bbox=(x, y, width, height),
            tile_id=tile_id, region=region,
        ))
    return rows


def main():
    parser = argparse.ArgumentParser(description="Select and label tile boxes locally")
    parser.add_argument("image")
    parser.add_argument("--dataset", default="dataset/tiles_v0_1")
    parser.add_argument("--region", required=True,
                        choices=("hand_region", "draw_region", "gold_region"))
    parser.add_argument("--suggest", action="store_true",
                        help="Offer a local template-match suggestion when labels exist")
    args = parser.parse_args()
    rows = annotate(args.image, args.dataset, args.region, suggestions=args.suggest)
    print(f"Saved {len(rows)} labels")


if __name__ == "__main__":
    main()
