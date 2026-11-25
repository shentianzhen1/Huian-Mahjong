"""Export SHA-locked, reviewer-selected PUBLIC FACE samples to PRIVATE storage.

Reviewer-selected coordinates are NOT machine detections or approved identities.
No action truth, tile guess, drive identifier or raw pixels enter GitHub.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from workspace.vision.public_source_lineage import load_lineage, verify_local_source

_SCHEMA = "source_public_review_samples_v0_1"


def export_review_samples(*, video: str | Path, manifest_path: str | Path,
                          registry_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    config = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if (not isinstance(config, dict) or config.get("schema_version") != _SCHEMA
            or config.get("development_only") is not True
            or config.get("excluded_from_formal_promotion") is not True
            or not isinstance(config.get("samples"), list)
            or not config["samples"]):
        raise ValueError("unsupported development public sample manifest")
    registry = load_lineage(registry_path)
    record = registry.get(config.get("source_session"))
    if (record is None or record.source_sha256 != config.get("source_sha256")
            or record.review_exposure != "previously_inspected"):
        raise ValueError("review samples must be bound to a previously-inspected known source")
    size = config.get("frame_size")
    if (not isinstance(size, list) or len(size) != 2
            or any(type(v) is not int or v <= 0 for v in size)):
        raise ValueError("frame_size must be positive exact pixels")
    names: set[str] = set()
    for row in config["samples"]:
        if (not isinstance(row, dict) or set(row) != {"sample_id", "frame", "pixel_bbox", "screen_side_actor", "region"}
                or not isinstance(row["sample_id"], str)
                or not row["sample_id"].replace("_", "").isalnum()
                or row["sample_id"] in names
                or type(row["frame"]) is not int or row["frame"] < 0
                or row["screen_side_actor"] not in {"opponent", "player"}
                or row["region"] != "public_single"
                or not isinstance(row["pixel_bbox"], list)
                or len(row["pixel_bbox"]) != 4
                or any(type(v) is not int for v in row["pixel_bbox"])):
            raise ValueError("invalid or duplicate reviewed source sample")
        x, y, width, height = row["pixel_bbox"]
        if x < 0 or y < 0 or width < 10 or height < 10 or x + width > size[0] or y + height > size[1]:
            raise ValueError("sample face bbox invalid or outside source")
        names.add(row["sample_id"])
    dest = Path(output_dir).resolve()
    repository = Path(__file__).resolve().parents[2]
    if dest == repository or repository in dest.parents:
        raise ValueError("private sample export must remain outside repository")
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        raise ValueError("private sample output must be an empty directory")
    verify_local_source(video, record)  # Before any video decode or files written.

    import cv2
    import numpy as np
    from PIL import Image

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError("source is not a decodable video")
    entries: list[dict[str, Any]] = []
    try:
        if (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))) != tuple(size):
            raise ValueError("review sample resolution mismatch")
        frames: dict[int, Any] = {}
        for row in config["samples"]:
            index = row["frame"]
            if index not in frames:
                if not cap.set(cv2.CAP_PROP_POS_FRAMES, index):
                    raise ValueError("cannot seek to sample frame")
                ok, bgr = cap.read()
                if not ok:
                    raise ValueError("missing sample source frame")
                frames[index] = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            x, y, width, height = row["pixel_bbox"]
            expected = frames[index][y:y+height, x:x+width]
            if expected.shape != (height, width, 3):
                raise ValueError("invalid cropped source frame")
            dest.mkdir(parents=True, exist_ok=True)
            filename = row["sample_id"] + ".png"
            image_path = dest / filename
            Image.fromarray(expected).save(image_path)
            with Image.open(image_path) as decoded:
                if not np.array_equal(expected, np.asarray(decoded.convert("RGB"))):
                    raise ValueError("private crop/source pixel roundtrip mismatch")
            entries.append({
                **row, "crop_file": filename,
                "crop_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                "crop_pixels_verified": True, "tile_id": None,
                "turn_actor": None, "action_kind": None, "review_status": "pending",
            })
    finally:
        cap.release()
    output = {
        "schema_version": _SCHEMA, "source_session": record.source_session,
        "source_sha256": record.source_sha256, "match_group": record.match_group,
        "source_disjoint_holdout": False, "development_only": True,
        "formal_promotion_evidence": False, "safe_for_executor": False,
        "selection_kind": "manually_reviewed_source_frame_geometry_not_machine_predictions",
        "samples": entries,
    }
    (dest / "review_samples.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("video", "manifest", "registry", "output_dir"):
        parser.add_argument("--" + name.replace("_", "-"), required=True)
    args = parser.parse_args()
    result = export_review_samples(video=args.video, manifest_path=args.manifest,
                                   registry_path=args.registry, output_dir=args.output_dir)
    print(json.dumps({"samples": len(result["samples"]), "formal_promotion_evidence": False,
                      "safe_for_executor": False}, indent=2))


if __name__ == "__main__":
    main()
