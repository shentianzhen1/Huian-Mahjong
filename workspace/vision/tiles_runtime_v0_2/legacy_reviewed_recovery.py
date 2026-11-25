"""Recover human-reviewed legacy V0.1 tile labels into Runtime V0.2 safely.

The old V0.1 raw label/ROI tree was intentionally local-only. This helper lets a
developer reuse that already-reviewed evidence without weakening Runtime V0.2
provenance rules.

Default mode is scan-only: it writes candidate crops/contact sheets below the
ignored Runtime work directory and DOES NOT modify labels.jsonl or templates.
Promotion requires explicit approval and an explicit logical source session.
Several clips from one match must use the same logical session.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

from PIL import Image, ImageDraw

from workspace.vision.tiles_v0_1.labels import approved_labels
from workspace.vision.tiles_v0_1.taxonomy import HONORS, SUITED


STANDARD_CLASSES = frozenset(SUITED) | frozenset(HONORS)
REGION_DIR = {
    "hand_region": "hand",
    "draw_region": "draw",
    "draw_visual": "draw",
    "gold_region": "gold",
}
SESSION_RE = re.compile(r"^[A-Za-z0-9_.-]{3,96}$")
MAX_TILE_CROP = (180, 200)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _crop_legacy_label(legacy_root: Path, row: dict) -> Image.Image:
    relative = Path(str(row.get("image", "")))
    if relative.is_absolute():
        raise ValueError("legacy label image must be dataset-relative")
    source = legacy_root / relative
    if not source.is_file():
        raise FileNotFoundError(source)
    bbox = row.get("bbox")
    if (
        not isinstance(bbox, list)
        or len(bbox) != 4
        or any(isinstance(value, bool) or not isinstance(value, int) for value in bbox)
    ):
        raise ValueError("legacy bbox must contain four integers")
    x, y, width, height = bbox
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        raise ValueError("legacy bbox must have positive dimensions")
    with Image.open(source) as image:
        image = image.convert("RGB")
        if x + width > image.width or y + height > image.height:
            raise ValueError("legacy bbox exceeds source ROI bounds")
        if width > MAX_TILE_CROP[0] or height > MAX_TILE_CROP[1]:
            raise ValueError("legacy crop is too large for tile-only recovery")
        return image.crop((x, y, x + width, y + height))


def scan_legacy_class(
    legacy_root: str | Path,
    runtime_root: str | Path,
    *,
    tile_id: str = "M2",
) -> dict:
    """Create local-only recovery candidates from approved legacy labels."""
    if tile_id not in STANDARD_CLASSES:
        raise ValueError(f"unsupported standard tile_id: {tile_id}")

    legacy = Path(legacy_root)
    runtime = Path(runtime_root)
    work = runtime / "work" / "legacy_reviewed_recovery" / tile_id
    crops = work / "crops"
    crops.mkdir(parents=True, exist_ok=True)

    candidates = []
    skipped = []
    for index, row in enumerate(approved_labels(legacy)):
        if row.get("tile_id") != tile_id:
            continue
        region = row.get("region")
        if region not in REGION_DIR:
            skipped.append({
                "legacy_index": index,
                "reason": "unsupported_region",
                "region": region,
            })
            continue
        try:
            crop = _crop_legacy_label(legacy, row)
        except (FileNotFoundError, ValueError) as exc:
            skipped.append({
                "legacy_index": index,
                "reason": f"{type(exc).__name__}: {exc}",
            })
            continue

        image_rel = Path(str(row["image"]))
        legacy_image = legacy / image_rel
        source_hash = _sha256(legacy_image)
        identity = json.dumps(
            {
                "legacy_image_sha256": source_hash,
                "source_frame": row.get("source_frame"),
                "bbox": row["bbox"],
                "tile_id": tile_id,
                "region": region,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        candidate_id = "legacy_" + hashlib.sha256(
            identity.encode("utf-8")
        ).hexdigest()[:16]
        crop_path = crops / f"{candidate_id}_{tile_id}.png"
        crop.save(crop_path, format="PNG")
        candidates.append({
            "id": candidate_id,
            "tile_id": tile_id,
            "region": "draw_visual" if region == "draw_region" else region,
            "source_frame": row.get("source_frame"),
            "bbox": list(row["bbox"]),
            "legacy_slot": row.get("slot"),
            "legacy_source_session_present": bool(row.get("source_session")),
            "legacy_image_sha256": source_hash,
            "crop": crop_path.relative_to(work).as_posix(),
            "requires_reapproval": True,
        })

    columns, cell_width, cell_height = 6, 150, 150
    rows_count = max(1, (len(candidates) + columns - 1) // columns)
    sheet = Image.new("RGB", (columns * cell_width, rows_count * cell_height), "white")
    draw = ImageDraw.Draw(sheet)
    for index, item in enumerate(candidates):
        with Image.open(work / item["crop"]) as source:
            image = source.convert("RGB")
        scale = min(105 / image.width, 100 / image.height)
        preview = image.resize(
            (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
        )
        x = (index % columns) * cell_width
        y = (index // columns) * cell_height
        sheet.paste(preview, (x + (cell_width - preview.width) // 2, y + 2))
        draw.text((x + 4, y + 108), item["id"], fill="black")
        draw.text((x + 4, y + 124), item["region"], fill="black")
    sheet_path = work / "contact_sheet.jpg"
    sheet.save(sheet_path, quality=92)

    plan = {
        "schema_version": "vision_runtime_v0_2_legacy_reviewed_recovery_v0_1",
        "tile_id": tile_id,
        "candidate_count": len(candidates),
        "skipped_count": len(skipped),
        "candidate_labels_are_unapproved": True,
        "logical_session_required_for_promotion": True,
        "same_match_clips_must_share_one_logical_session": True,
        "contact_sheet": sheet_path.relative_to(work).as_posix(),
        "candidates": candidates,
        "skipped": skipped,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }
    _write_json(work / "plan.json", plan)
    return plan


def promote_candidate(
    runtime_root: str | Path,
    *,
    tile_id: str,
    candidate_id: str,
    logical_session: str,
    reviewer: str,
    approved: bool,
) -> dict:
    """Promote one re-reviewed local legacy crop into Runtime V0.2."""
    if not approved:
        raise ValueError("explicit approved=True/--approved is required")
    if tile_id not in STANDARD_CLASSES:
        raise ValueError(f"unsupported standard tile_id: {tile_id}")
    if not SESSION_RE.fullmatch(logical_session):
        raise ValueError("logical_session must be an anonymized 3-96 character identifier")
    if not reviewer.strip():
        raise ValueError("reviewer is required")

    runtime = Path(runtime_root)
    work = runtime / "work" / "legacy_reviewed_recovery" / tile_id
    plan_path = work / "plan.json"
    if not plan_path.is_file():
        raise ValueError("scan plan missing; run scan before promotion")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    matches = [
        item for item in plan.get("candidates", [])
        if item.get("id") == candidate_id and item.get("tile_id") == tile_id
    ]
    if len(matches) != 1:
        raise ValueError("candidate_id is not uniquely present in the scan plan")
    item = matches[0]
    crop = work / item["crop"]
    if not crop.is_file():
        raise ValueError("candidate crop is missing")

    region = item["region"]
    relative = Path("templates") / REGION_DIR[region] / f"{candidate_id}_{tile_id}.png"
    asset = runtime / relative
    labels_path = runtime / "labels.jsonl"
    labels = _read_jsonl(labels_path)
    if any(row.get("id") == candidate_id for row in labels):
        raise ValueError("candidate is already present in Runtime labels")

    asset.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(crop, asset)
    asset_sha = _sha256(asset)
    source_hash = item["legacy_image_sha256"]
    row = {
        "id": candidate_id,
        "image": relative.as_posix(),
        "source_id": f"src_legacy_{source_hash[:16]}",
        "source_session": logical_session,
        "source_frame": item.get("source_frame"),
        "bbox": list(item["bbox"]),
        "slot": item.get("legacy_slot"),
        "tile_id": tile_id,
        "region": region,
        "approved": True,
        "status": "approved",
        "reviewer": reviewer,
        "sha256": source_hash,
        "asset_sha256": asset_sha,
        "crop_bbox": list(item["bbox"]),
        "crop_policy": "legacy_reviewed_exact_bbox_v0_1",
        "provenance": "legacy_v0_1_reviewed_label_reapproved_for_runtime_v0_2",
        "asset_role": "development_prototype_only",
    }
    with labels_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recover a human-reviewed local V0.1 class into Runtime V0.2"
    )
    parser.add_argument("--legacy-dataset", default="dataset/tiles_v0_1")
    parser.add_argument("--runtime-dataset", default="dataset/tiles_runtime_v0_2")
    parser.add_argument("--tile-id", default="M2")
    parser.add_argument("--approve-candidate")
    parser.add_argument("--logical-session")
    parser.add_argument("--reviewer", default="manual")
    parser.add_argument("--approved", action="store_true")
    args = parser.parse_args()

    if args.approve_candidate:
        if not args.logical_session:
            raise ValueError(
                "--logical-session is required for promotion; all clips from one "
                "match must reuse the same logical session"
            )
        result = promote_candidate(
            args.runtime_dataset,
            tile_id=args.tile_id,
            candidate_id=args.approve_candidate,
            logical_session=args.logical_session,
            reviewer=args.reviewer,
            approved=args.approved,
        )
    else:
        result = scan_legacy_class(
            args.legacy_dataset,
            args.runtime_dataset,
            tile_id=args.tile_id,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
