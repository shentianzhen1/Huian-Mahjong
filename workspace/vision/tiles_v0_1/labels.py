"""Reviewable JSONL labels for manually selected tile rectangles."""
import json
from pathlib import Path

from .taxonomy import category_for


def append_label(dataset_root, *, image, bbox, tile_id, region, status="approved",
                 source_frame=None, source_session=None, annotator="manual"):
    if region not in ("hand_region", "draw_region", "gold_region"):
        raise ValueError(f"Unknown region: {region}")
    if status not in ("approved", "review", "rejected"):
        raise ValueError(f"Unknown label status: {status}")
    if len(bbox) != 4 or any(not isinstance(value, int) for value in bbox):
        raise ValueError("bbox must be four integer values")
    x, y, width, height = bbox
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        raise ValueError("bbox must have positive dimensions")
    root = Path(dataset_root)
    row = {
        "image": str(image).replace("\\", "/"), "bbox": list(bbox),
        "tile_id": tile_id, "category": category_for(tile_id), "region": region,
        "status": status, "source_frame": source_frame,
        "source_session": source_session, "annotator": annotator,
    }
    path = root / "labels" / "tiles.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def approved_labels(dataset_root):
    path = Path(dataset_root) / "labels" / "tiles.jsonl"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        rows = (json.loads(line) for line in stream if line.strip())
        return [row for row in rows if row.get("status") == "approved"]
