"""Prepare and manually review a small Runtime V0.2 tile-ID queue.

Candidate crops and review drafts stay below ignored ``work/``.  Only an
explicit human approval writes a tile-only template and an approved label.
No full frame is copied into the tracked dataset.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict, deque
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageTk
import tkinter as tk
from tkinter import messagebox, ttk

from workspace.vision.tiles_v0_1.taxonomy import HONORS, SUITED
from workspace.vision.tiles_v0_1.template_classifier import TemplateTileClassifier

from .phase5b_holdout import locate_sources


TILE_IDS = tuple(SUITED) + tuple(HONORS)
REGION_MAP = {
    "hand": ("hand", "hand_region"),
    "draw": ("draw", "draw_visual"),
    "draw_visual": ("draw", "draw_visual"),
    "gold": ("gold", "gold_region"),
}


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(path)


def _crop_frame(source: Path, frame_index: int, bbox: list[int]) -> Image.Image:
    capture = cv2.VideoCapture(str(source))
    capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame = capture.read()
    capture.release()
    if not ok:
        raise ValueError(f"Cannot read anonymized frame {frame_index}")
    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    x, y, width, height = bbox
    if x < 0 or y < 0 or x + width > image.width or y + height > image.height:
        raise ValueError("Geometry bbox is outside its source frame")
    return image.crop((x, y, x + width, y + height))


def _dhash(image: Image.Image) -> int:
    values = np.asarray(
        image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    )
    result = 0
    for row in range(8):
        for column in range(8):
            result = (result << 1) | int(values[row, column] > values[row, column + 1])
    return result


def prepare_candidates(dataset: Path, media_root: Path, limit: int = 96) -> dict:
    truth_path = dataset / "validation" / "holdout" / "geometry_holdout_ground_truth_v0_2.jsonl"
    work = dataset / "work" / "phase6_tile_review"
    crop_dir = work / "crops"
    crop_dir.mkdir(parents=True, exist_ok=True)
    sources = locate_sources(media_root)
    candidates = []
    for row in _read_jsonl(truth_path):
        frame_state = row.get("frame_state", row.get("trust_state"))
        if not row.get("approved") or frame_state != "trusted":
            continue
        source_sha = row.get("source_sha256")
        source = sources.get(source_sha)
        if source is None:
            continue
        grouped: dict[str, list[dict]] = defaultdict(list)
        for component in row.get("components", []):
            region = component.get("region_candidate")
            if region in REGION_MAP:
                grouped[region].append(component)
        for region, components in grouped.items():
            components.sort(key=lambda item: (item["pixel_bbox"][0], item["pixel_bbox"][1]))
            for slot, component in enumerate(components):
                bbox = [int(value) for value in component["pixel_bbox"]]
                crop = _crop_frame(source, int(row["source_frame"]), bbox)
                gray = cv2.cvtColor(np.asarray(crop.convert("RGB")), cv2.COLOR_RGB2GRAY)
                sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
                fingerprint = _dhash(crop)
                identity = (
                    f"{row['source_session']}:{row['source_frame']}:{region}:"
                    + ",".join(map(str, bbox))
                )
                candidate_id = "tile_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
                crop_path = crop_dir / f"{candidate_id}.png"
                crop.save(crop_path)
                candidates.append({
                    "id": candidate_id,
                    "source_id": row["source_id"],
                    "source_session": row["source_session"],
                    "source_frame": int(row["source_frame"]),
                    "source_sha256": source_sha,
                    "bbox": bbox,
                    "slot": slot,
                    "region_candidate": REGION_MAP[region][1],
                    "crop": crop_path.relative_to(work).as_posix(),
                    "sharpness": round(sharpness, 3),
                    "dhash": f"{fingerprint:016x}",
                })

    _write_jsonl(work / "candidate_pool.jsonl", candidates)

    # Round-robin sessions prevents one recording from dominating the small
    # review queue. Draw candidates are retained first because they are rare.
    candidates.sort(key=lambda item: (item["region_candidate"] != "draw_visual", -item["sharpness"]))
    queues: dict[str, deque] = defaultdict(deque)
    for item in candidates:
        queues[item["source_session"]].append(item)
    chosen = []
    session_order = sorted(queues)
    while len(chosen) < min(limit, len(candidates)) and session_order:
        next_order = []
        for session in session_order:
            if queues[session] and len(chosen) < limit:
                candidate = queues[session].popleft()
                # Avoid near-identical crops from the same session while still
                # retaining cross-session examples of the same tile class.
                fp = int(candidate["dhash"], 16)
                if all(
                    other["source_session"] != session
                    or (fp ^ int(other["dhash"], 16)).bit_count() >= 3
                    for other in chosen
                ):
                    chosen.append(candidate)
            if queues[session]:
                next_order.append(session)
        session_order = next_order

    plan = {
        "schema_version": "vision_runtime_v0_2_phase6_tile_review",
        "purpose": "Small human-approved tile-ID queue for the read-only test build.",
        "candidate_count": len(chosen),
        "source_sessions": sorted({item["source_session"] for item in chosen}),
        "regions": dict(__import__("collections").Counter(item["region_candidate"] for item in chosen)),
        "human_approval_required": True,
        "safe_for_executor": False,
        "candidates": chosen,
    }
    (work / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return plan


def build_gap_sheets(dataset: Path) -> dict:
    work = dataset / "work" / "phase6_tile_review"
    candidates = _read_jsonl(work / "candidate_pool.jsonl")
    reviews = {row["id"]: row for row in _read_jsonl(work / "reviews.jsonl")}
    remaining = [item for item in candidates if reviews.get(item["id"], {}).get("status") != "approved"]
    page_dir = work / "gap_sheets"
    page_dir.mkdir(parents=True, exist_ok=True)
    page_size, columns, cell_width, cell_height = 48, 8, 145, 135
    pages = []
    for page_start in range(0, len(remaining), page_size):
        items = remaining[page_start:page_start + page_size]
        rows_count = (len(items) + columns - 1) // columns
        sheet = Image.new("RGB", (columns * cell_width, rows_count * cell_height), "white")
        draw = ImageDraw.Draw(sheet)
        for index, item in enumerate(items):
            image = Image.open(work / item["crop"]).convert("RGB")
            scale = min(105 / image.width, 96 / image.height)
            preview = image.resize((round(image.width * scale), round(image.height * scale)))
            x = (index % columns) * cell_width
            y = (index // columns) * cell_height
            sheet.paste(preview, (x + (cell_width - preview.width) // 2, y + 1))
            draw.text((x + 4, y + 101), item["id"].removeprefix("tile_")[:8], fill="black")
            draw.text((x + 4, y + 116), f"{item['source_session'][-4:]} {item['region_candidate'][:4]}", fill="black")
        page = page_dir / f"gap_{page_start // page_size + 1:02d}.jpg"
        sheet.save(page, quality=92)
        pages.append(page.relative_to(work).as_posix())
    index = {
        "schema_version": "vision_runtime_v0_2_phase6_gap_sheets",
        "remaining_candidates": len(remaining),
        "pages": pages,
        "candidate_labels_are_unapproved": True,
    }
    (page_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return index


def build_targeted_plan(
    dataset: Path, prefixes: list[str], *, plan_name: str = "gap_plan.json"
) -> dict:
    work = dataset / "work" / "phase6_tile_review"
    pool = _read_jsonl(work / "candidate_pool.jsonl")
    selected = []
    missing = []
    for specification in prefixes:
        target_hint, separator, prefix = specification.partition("=")
        if not separator:
            prefix, target_hint = specification, ""
        matches = [
            item for item in pool
            if item["id"].removeprefix("tile_").startswith(prefix)
        ]
        if matches:
            item = dict(matches[0])
            if target_hint:
                item["target_hint"] = target_hint
            selected.append(item)
        else:
            missing.append(prefix)
    plan = {
        "schema_version": "vision_runtime_v0_2_phase6_targeted_gap_review",
        "purpose": "Human confirmation candidates for the eight missing standard tile classes.",
        "candidate_count": len(selected),
        "requested_prefixes_not_found": missing,
        "human_approval_required": True,
        "safe_for_executor": False,
        "candidates": selected,
    }
    (work / plan_name).write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return plan


class TileReviewApp(tk.Tk):
    def __init__(self, dataset: Path, media_root: Path, *, plan_name: str = "plan.json", review_name: str = "reviews.jsonl"):
        super().__init__()
        self.dataset = dataset
        self.work = dataset / "work" / "phase6_tile_review"
        plan_path = self.work / plan_name
        if not plan_path.exists():
            prepare_candidates(dataset, media_root)
        self.plan = json.loads(plan_path.read_text(encoding="utf-8"))
        self.items = self.plan["candidates"]
        self.review_path = self.work / review_name
        self.reviews = {row["id"]: row for row in _read_jsonl(self.review_path)}
        self.index = next((i for i, item in enumerate(self.items) if self.reviews.get(item["id"], {}).get("status") not in {"approved", "skipped"}), 0)
        self.tile_id = tk.StringVar()
        self.suggestion = tk.StringVar(value="suggestion: unavailable")
        self.title("Huian Vision V0.2 — Minimal Tile ID Review")
        self.full_canvas = tk.Canvas(self, width=900, height=560, background="black")
        self.full_canvas.grid(row=0, column=0, columnspan=7)
        self.crop_label = ttk.Label(self)
        self.crop_label.grid(row=0, column=7, padx=12)
        ttk.Label(self, text="Tile ID").grid(row=1, column=0)
        self.combo = ttk.Combobox(self, textvariable=self.tile_id, values=TILE_IDS, width=10)
        self.combo.grid(row=1, column=1)
        ttk.Label(self, textvariable=self.suggestion).grid(row=1, column=2, columnspan=2)
        ttk.Button(self, text="Approve & Next", command=self.approve_next).grid(row=2, column=0)
        ttk.Button(self, text="Skip / Unknown", command=self.skip_next).grid(row=2, column=1)
        ttk.Button(self, text="Previous", command=lambda: self.move(-1)).grid(row=2, column=2)
        ttk.Button(self, text="Next", command=lambda: self.move(1)).grid(row=2, column=3)
        self.status = ttk.Label(self)
        self.status.grid(row=2, column=4, columnspan=4)
        self.sources = locate_sources(media_root)
        try:
            self.classifier = TemplateTileClassifier.from_dataset(dataset)
        except ValueError:
            self.classifier = None
        self.show_current()

    def current(self) -> dict:
        return self.items[self.index]

    def _source_frame(self, item: dict) -> Image.Image:
        source = self.sources.get(item["source_sha256"])
        if source is None:
            raise ValueError("Local source media is unavailable")
        capture = cv2.VideoCapture(str(source))
        capture.set(cv2.CAP_PROP_POS_FRAMES, item["source_frame"])
        ok, frame = capture.read()
        capture.release()
        if not ok:
            raise ValueError("Local source frame cannot be read")
        return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    def show_current(self) -> None:
        item = self.current()
        original = self._source_frame(item)
        scale = min(900 / original.width, 560 / original.height)
        display = original.resize((round(original.width * scale), round(original.height * scale)))
        draw = ImageDraw.Draw(display)
        x, y, width, height = item["bbox"]
        draw.rectangle((x * scale, y * scale, (x + width) * scale, (y + height) * scale), outline="#38e878", width=4)
        self.full_photo = ImageTk.PhotoImage(display)
        self.full_canvas.delete("all")
        self.full_canvas.create_image(0, 0, anchor="nw", image=self.full_photo)
        crop = Image.open(self.work / item["crop"]).convert("RGB")
        preview = crop.resize((crop.width * 5, crop.height * 5), Image.Resampling.NEAREST)
        self.crop_photo = ImageTk.PhotoImage(preview)
        self.crop_label.config(image=self.crop_photo)
        review = self.reviews.get(item["id"], {})
        self.tile_id.set(review.get("tile_id", ""))
        if self.classifier is not None:
            try:
                guess = self.classifier.classify(crop, region=item["region_candidate"])
                self.suggestion.set(f"suggestion only: {guess.tile_id} ({guess.confidence:.2f})")
            except ValueError:
                self.suggestion.set("suggestion: unavailable for this region")
        approved = sum(row.get("status") == "approved" for row in self.reviews.values())
        skipped = sum(row.get("status") == "skipped" for row in self.reviews.values())
        hint = f" | target candidate {item['target_hint']}" if item.get("target_hint") else ""
        self.status.config(text=f"{self.index + 1}/{len(self.items)} | approved {approved} | skipped {skipped} | {item['region_candidate']}{hint}")

    def _save_reviews(self) -> None:
        _write_jsonl(self.review_path, [self.reviews[key] for key in sorted(self.reviews)])

    def approve_next(self) -> None:
        tile_id = self.tile_id.get().strip().upper()
        if tile_id not in TILE_IDS:
            messagebox.showerror("Invalid tile", "Choose one of the 34 standard tile IDs.")
            return
        item = self.current()
        subdir = {"hand_region": "hand", "draw_visual": "draw", "gold_region": "gold"}[item["region_candidate"]]
        relative_asset = Path("templates") / subdir / f"{item['id']}_{tile_id}.png"
        target = self.dataset / relative_asset
        target.parent.mkdir(parents=True, exist_ok=True)
        crop = Image.open(self.work / item["crop"]).convert("RGB")
        crop.save(target)
        asset_sha = hashlib.sha256(target.read_bytes()).hexdigest()
        label = {
            "id": item["id"], "image": relative_asset.as_posix(),
            "source_id": item["source_id"], "source_session": item["source_session"],
            "source_frame": item["source_frame"], "bbox": item["bbox"], "slot": item["slot"],
            "tile_id": tile_id, "region": item["region_candidate"],
            "approved": True, "status": "approved", "reviewer": "manual",
            "sha256": item["source_sha256"], "asset_sha256": asset_sha,
        }
        labels_path = self.dataset / "labels.jsonl"
        labels = _read_jsonl(labels_path)
        # A reviewer may revisit an item and correct its tile ID.  Remove only
        # the superseded, derived tile crop for this same candidate so a stale
        # filename cannot later be mistaken for another approved class.
        previous_assets = [
            self.dataset / row["image"]
            for row in labels
            if row.get("id") == item["id"] and row.get("image") != relative_asset.as_posix()
        ]
        labels = [row for row in labels if row.get("id") != item["id"]]
        labels.append(label)
        _write_jsonl(labels_path, labels)
        for previous_asset in previous_assets:
            if previous_asset.is_file():
                previous_asset.unlink()
        self.reviews[item["id"]] = {"id": item["id"], "status": "approved", "tile_id": tile_id}
        self._save_reviews()
        self.move(1)

    def skip_next(self) -> None:
        item = self.current()
        self.reviews[item["id"]] = {"id": item["id"], "status": "skipped"}
        self._save_reviews()
        self.move(1)

    def move(self, delta: int) -> None:
        self.index = max(0, min(len(self.items) - 1, self.index + delta))
        self.show_current()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="dataset/tiles_runtime_v0_2")
    parser.add_argument("--media-root", default="data/capture_validation")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--gap-sheets", action="store_true")
    parser.add_argument("--target-prefixes", nargs="*")
    parser.add_argument("--plan", default="plan.json")
    parser.add_argument("--reviews", default="reviews.jsonl")
    parser.add_argument("--limit", type=int, default=96)
    args = parser.parse_args()
    dataset = Path(args.dataset)
    media_root = Path(args.media_root)
    if args.target_prefixes is not None:
        print(json.dumps(
            build_targeted_plan(dataset, args.target_prefixes, plan_name=args.plan),
            ensure_ascii=False,
            indent=2,
        ))
    elif args.gap_sheets:
        print(json.dumps(build_gap_sheets(dataset), ensure_ascii=False, indent=2))
    elif args.prepare_only:
        plan = prepare_candidates(dataset, media_root, args.limit)
        print(json.dumps({key: plan[key] for key in ("candidate_count", "source_sessions", "regions")}, ensure_ascii=False, indent=2))
    else:
        TileReviewApp(dataset, media_root, plan_name=args.plan, review_name=args.reviews).mainloop()


if __name__ == "__main__":
    main()
