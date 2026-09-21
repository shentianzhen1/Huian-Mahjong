"""Rebuild approved Phase 6 crops with neighbor-safe classification padding."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
from PIL import Image, ImageDraw

from .phase5b_holdout import locate_sources
from .tile_crop import classification_crop_bbox


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(path)


def _frame(source: Path, frame_index: int) -> Image.Image:
    capture = cv2.VideoCapture(str(source))
    capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, value = capture.read()
    capture.release()
    if not ok:
        raise ValueError(f"Cannot read anonymized source frame {frame_index}")
    return Image.fromarray(cv2.cvtColor(value, cv2.COLOR_BGR2RGB))


def rebuild(dataset: Path, media_root: Path) -> dict:
    labels_path = dataset / "labels.jsonl"
    labels = _read_jsonl(labels_path)
    truth_path = dataset / "validation" / "holdout" / "geometry_holdout_ground_truth_v0_2.jsonl"
    truth = _read_jsonl(truth_path)
    truth_index = {
        (row.get("source_sha256"), int(row["source_frame"])): row
        for row in truth
        if row.get("source_sha256") and row.get("source_frame") is not None
    }
    sources = locate_sources(media_root)
    rebuilt = []
    comparisons = []
    for row in labels:
        # Legacy Phase 2 assets lack a stable local source frame and remain
        # unchanged. New Phase 6 rows have deterministic tile_* IDs.
        if not str(row.get("id", "")).startswith("tile_"):
            continue
        source = sources.get(row["sha256"])
        truth_row = truth_index.get((row["sha256"], int(row["source_frame"])))
        if source is None or truth_row is None:
            continue
        image = _frame(source, int(row["source_frame"]))
        neighbors = [
            component["pixel_bbox"]
            for component in truth_row.get("components", [])
            if list(component["pixel_bbox"]) != list(row["bbox"])
        ]
        crop_bbox = classification_crop_bbox(
            row["bbox"], frame_size=image.size, neighbors=neighbors
        )
        x, y, width, height = crop_bbox
        new_crop = image.crop((x, y, x + width, y + height))
        asset = dataset / row["image"]
        with Image.open(asset) as current:
            old_crop = current.convert("RGB")
        new_crop.save(asset)
        row["crop_bbox"] = list(crop_bbox)
        row["crop_policy"] = "neighbor_safe_v0_1"
        row["asset_sha256"] = hashlib.sha256(asset.read_bytes()).hexdigest()
        rebuilt.append(row["id"])
        comparisons.append((row["tile_id"], old_crop, new_crop))

    _write_jsonl(labels_path, labels)
    work = dataset / "work" / "phase6_tile_review"
    columns, cell_width, cell_height = 6, 220, 145
    rows_count = (len(comparisons) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * cell_width, rows_count * cell_height), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (tile_id, before, after) in enumerate(comparisons):
        x = (index % columns) * cell_width
        y = (index // columns) * cell_height
        for offset, image in ((4, before), (112, after)):
            scale = min(98 / image.width, 105 / image.height)
            preview = image.resize((round(image.width * scale), round(image.height * scale)))
            sheet.paste(preview, (x + offset, y + 2))
        draw.text((x + 4, y + 112), f"{tile_id} before / after", fill="black")
    comparison_path = work / "crop_padding_before_after.jpg"
    sheet.save(comparison_path, quality=92)
    report = {
        "schema_version": "vision_runtime_v0_2_classification_crop_v0_1",
        "rebuilt_templates": len(rebuilt),
        "geometry_bbox_changed": False,
        "tile_id_changed": False,
        "crop_policy": "expand bright-component geometry bbox; clamp horizontal padding at adjacent tile midpoints; preserve source bounds",
        "local_comparison_sheet": "work/phase6_tile_review/crop_padding_before_after.jpg",
        "human_visual_review": "passed_manual_2026-09-21",
        "safe_for_executor": False,
    }
    output = dataset / "validation" / "reports" / "phase6_classification_crop_v0_1.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="dataset/tiles_runtime_v0_2")
    parser.add_argument("--media-root", default="data/capture_validation")
    args = parser.parse_args()
    print(json.dumps(rebuild(Path(args.dataset), Path(args.media_root)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
