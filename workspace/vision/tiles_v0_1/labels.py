"""Reviewable JSONL labels for manually selected tile rectangles."""
import json
from pathlib import Path

from .taxonomy import category_for


REVIEWED_ADDITIONS_DIR = "labels_reviewed_additions"


def append_label(dataset_root, *, image, bbox, tile_id, region, status="approved",
                 source_frame=None, source_session=None, annotator="manual"):
    if region not in ("hand_region", "draw_region", "gold_region"):
        raise ValueError(f"Unknown region: {region}")
    if status not in ("approved", "review", "rejected"):
        raise ValueError(f"Unknown status: {status}")
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


def _label_paths(root: Path) -> list[Path]:
    """Return the primary labels file followed by optional reviewed additions."""
    legacy_path = root / "labels" / "tiles.jsonl"
    runtime_path = root / "labels.jsonl"
    primary = runtime_path if runtime_path.exists() else legacy_path

    paths: list[Path] = []
    if primary.exists():
        paths.append(primary)

    additions_dir = root / REVIEWED_ADDITIONS_DIR
    if additions_dir.is_dir():
        paths.extend(sorted(path for path in additions_dir.glob("*.jsonl") if path.is_file()))
    return paths


def approved_labels(dataset_root):
    root = Path(dataset_root)
    paths = _label_paths(root)
    if not paths:
        return []

    approved = []
    for path in paths:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("status") == "approved" or row.get("approved") is True:
                    approved.append(row)
    return approved
