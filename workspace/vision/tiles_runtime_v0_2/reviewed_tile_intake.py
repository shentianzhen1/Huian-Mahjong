"""Privacy-bounded intake for one manually reviewed Runtime V0.2 tile crop.

The private source image/video is never copied into the repository. Only the
exact reviewed tile rectangle plus anonymous provenance is persisted. Logical
source_session is caller-supplied on purpose: multiple clips from the same
match MUST reuse one session so they cannot self-validate as independent data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import cv2
from PIL import Image

from workspace.vision.tiles_v0_1.taxonomy import HONORS, SUITED


REGION_DIR = {
    "hand_region": "hand",
    "draw_visual": "draw",
    "draw_region": "draw",
    "gold_region": "gold",
}
STANDARD_CLASSES = frozenset(SUITED) | frozenset(HONORS)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
SESSION_RE = re.compile(r"^[A-Za-z0-9_.-]{3,96}$")
MAX_TILE_CROP = (180, 200)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_frame(source: Path, source_frame: int | None) -> Image.Image:
    if source.suffix.lower() in IMAGE_SUFFIXES:
        if source_frame not in (None, 0):
            raise ValueError("source_frame must be omitted or 0 for an image source")
        with Image.open(source) as image:
            return image.convert("RGB")

    if source_frame is None or isinstance(source_frame, bool) or source_frame < 0:
        raise ValueError("video sources require a non-negative source_frame")
    capture = cv2.VideoCapture(str(source))
    try:
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(source_frame))
        ok, frame = capture.read()
    finally:
        capture.release()
    if not ok:
        raise ValueError(f"cannot read source_frame {source_frame}")
    return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))


def _validate_bbox(bbox: tuple[int, int, int, int], size: tuple[int, int]) -> None:
    if len(bbox) != 4 or any(isinstance(value, bool) or not isinstance(value, int) for value in bbox):
        raise ValueError("bbox must contain four integers")
    x, y, width, height = bbox
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        raise ValueError("bbox must have positive dimensions inside the source")
    if x + width > size[0] or y + height > size[1]:
        raise ValueError("bbox exceeds source bounds")
    if width > MAX_TILE_CROP[0] or height > MAX_TILE_CROP[1]:
        raise ValueError("reviewed crop is too large to be a tile-only privacy asset")


def _load_labels(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def intake_reviewed_tile(
    dataset_root: str | Path,
    *,
    source: str | Path,
    source_session: str,
    source_frame: int | None,
    bbox: tuple[int, int, int, int],
    slot: int,
    tile_id: str,
    region: str,
    reviewer: str,
    approved: bool,
    gold_skin_only: bool = False,
) -> dict:
    """Persist one explicitly approved tile-only crop and anonymous provenance."""
    if not approved:
        raise ValueError("explicit approved=True/--approved is required")
    if tile_id not in STANDARD_CLASSES:
        raise ValueError(f"unsupported standard tile_id: {tile_id}")
    if region not in REGION_DIR:
        raise ValueError(f"unsupported region: {region}")
    canonical_region = "draw_visual" if region == "draw_region" else region
    if not isinstance(gold_skin_only, bool):
        raise ValueError("gold_skin_only must be boolean")
    if gold_skin_only and canonical_region not in {"hand_region", "draw_visual"}:
        raise ValueError("gold_skin_only is valid only for concealed hand/draw geometry")
    if isinstance(slot, bool) or not isinstance(slot, int) or slot < 0:
        raise ValueError("slot must be a non-negative integer")
    if not reviewer.strip():
        raise ValueError("reviewer is required")
    if not SESSION_RE.fullmatch(source_session):
        raise ValueError("source_session must be an anonymized 3-96 character identifier")

    source = Path(source)
    if not source.is_file():
        raise ValueError("source must be an existing private image or video file")
    source_sha = _sha256(source)
    source_id = f"src_{source_sha[:16]}"
    image = _read_frame(source, source_frame)
    _validate_bbox(bbox, image.size)

    dataset = Path(dataset_root)
    labels_path = dataset / "labels.jsonl"
    labels_path.parent.mkdir(parents=True, exist_ok=True)
    labels = _load_labels(labels_path)
    normalized_frame = None if source.suffix.lower() in IMAGE_SUFFIXES else int(source_frame)
    for row in labels:
        if (
            row.get("sha256") == source_sha
            and row.get("source_frame") == normalized_frame
            and list(row.get("bbox", ())) == list(bbox)
            and row.get("tile_id") == tile_id
        ):
            raise ValueError("the reviewed source rectangle is already present")

    x, y, width, height = bbox
    crop = image.crop((x, y, x + width, y + height))
    identity_seed = json.dumps(
        {
            "sha256": source_sha,
            "source_frame": normalized_frame,
            "bbox": list(bbox),
            "tile_id": tile_id,
            "region": canonical_region,
            "gold_skin_only": gold_skin_only,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    sample_id = "tile_" + hashlib.sha256(identity_seed).hexdigest()[:16]
    relative = Path("templates") / REGION_DIR[region] / f"{sample_id}_{tile_id}.png"
    asset = dataset / relative
    asset.parent.mkdir(parents=True, exist_ok=True)
    if asset.exists():
        raise ValueError("deterministic reviewed asset already exists")
    crop.save(asset, format="PNG")
    asset_sha = _sha256(asset)

    row = {
        "id": sample_id,
        "image": relative.as_posix(),
        "source_id": source_id,
        "source_session": source_session,
        "source_frame": normalized_frame,
        "bbox": list(bbox),
        "slot": slot,
        "tile_id": tile_id,
        "region": canonical_region,
        "approved": True,
        "status": "approved",
        "reviewer": reviewer,
        "sha256": source_sha,
        "asset_sha256": asset_sha,
        "crop_bbox": list(bbox),
        "crop_policy": "reviewed_exact_bbox_v0_1",
        "gold_skin_only": gold_skin_only,
        "asset_role": (
            "gold_identity_only"
            if gold_skin_only
            else "development_prototype_only"
        ),
    }
    with labels_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Persist one manually reviewed, tile-only Runtime V0.2 crop"
    )
    parser.add_argument("--dataset", default="dataset/tiles_runtime_v0_2")
    parser.add_argument("--source", required=True)
    parser.add_argument("--source-session", required=True)
    parser.add_argument("--source-frame", type=int)
    parser.add_argument("--bbox", nargs=4, type=int, metavar=("X", "Y", "W", "H"), required=True)
    parser.add_argument("--slot", type=int, required=True)
    parser.add_argument("--tile-id", required=True)
    parser.add_argument("--region", choices=tuple(REGION_DIR), required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--approved", action="store_true")
    parser.add_argument(
        "--gold-skin-only",
        action="store_true",
        help=(
            "store a yellow Gold-skinned concealed tile only in the "
            "Gold-normalized identity bank; do not train ordinary hand/draw identity"
        ),
    )
    args = parser.parse_args()
    row = intake_reviewed_tile(
        args.dataset,
        source=args.source,
        source_session=args.source_session,
        source_frame=args.source_frame,
        bbox=tuple(args.bbox),
        slot=args.slot,
        tile_id=args.tile_id,
        region=args.region,
        reviewer=args.reviewer,
        approved=args.approved,
        gold_skin_only=args.gold_skin_only,
    )
    print(json.dumps(row, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
