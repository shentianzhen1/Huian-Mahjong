"""Blind, human-only geometry review for the Phase 5C holdout.

This UI intentionally does *not* import or run the geometry detector.  Review
starts with an empty canvas over each original local frame; only explicit human
edits become geometry truth.  Detector evaluation is permitted only after all
holdout rows are approved.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageTk
import tkinter as tk
from tkinter import messagebox, ttk

from .geometry_schema import compatibility_view, geometry_counts, new_geometry_row_fields
from .phase5b_holdout import locate_sources


COLORS = {
    "hand": "#38e878", "draw_visual": "#ff9f1c", "gold": "#ffd60a",
    "meld": "#64d2ff", "unknown": "#ff453a",
}


def load_rows(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    return {
        row["id"]: row
        for row in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)
    }


def save_rows(path: Path, rows: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        "".join(json.dumps(rows[key], ensure_ascii=False) + "\n" for key in sorted(rows)),
        encoding="utf-8",
    )
    temporary.replace(path)


class BlindHoldoutReview(tk.Tk):
    def __init__(self, dataset: Path, media_root: Path):
        super().__init__()
        self.dataset = dataset
        self.plan_path = dataset / "validation" / "holdout" / "phase5b_geometry_holdout_plan_v0_2.json"
        self.truth_path = dataset / "validation" / "holdout" / "geometry_holdout_ground_truth_v0_2.jsonl"
        self.plan = json.loads(self.plan_path.read_text(encoding="utf-8"))
        self.items = self.plan["frames"]
        self.reviews, self.index = load_rows(self.truth_path), 0
        self.sources = locate_sources(media_root)
        self.components, self.selected, self.drag_start, self.frozen = [], None, None, False
        self.region = tk.StringVar(value="hand")
        self.trust = tk.StringVar(value="trusted")
        self.hand_count = tk.StringVar(value="0")
        self.draw_visual_count = tk.StringVar(value="0")
        self.concealed_count = tk.StringVar(value="0")
        self.title("Huian Vision V0.2 — Phase 5C Blind Holdout Review")
        self.canvas = tk.Canvas(self, width=1000, height=620, background="black")
        self.canvas.grid(row=0, column=0, columnspan=8)
        ttk.Label(self, text="Region").grid(row=1, column=0)
        ttk.Combobox(self, textvariable=self.region, values=("hand", "draw_visual", "gold", "meld", "unknown"), width=12).grid(row=1, column=1)
        ttk.Label(self, text="Frame state").grid(row=1, column=2)
        ttk.Combobox(self, textvariable=self.trust, values=("trusted", "occluded", "animation"), width=10).grid(row=1, column=3)
        ttk.Label(self, text="hand / draw_visual / concealed").grid(row=1, column=4)
        ttk.Label(self, textvariable=self.hand_count).grid(row=1, column=5)
        ttk.Label(self, textvariable=self.draw_visual_count).grid(row=1, column=6)
        ttk.Label(self, textvariable=self.concealed_count).grid(row=1, column=7)
        self.delete_button = ttk.Button(self, text="Delete selected", command=self.delete_selected); self.delete_button.grid(row=2, column=0)
        self.region_button = ttk.Button(self, text="Apply region", command=self.apply_region); self.region_button.grid(row=2, column=1)
        self.save_button = ttk.Button(self, text="Save draft", command=self.save_draft); self.save_button.grid(row=2, column=2)
        self.approve_button = ttk.Button(self, text="Approve & Next", command=self.approve_next); self.approve_button.grid(row=2, column=3)
        ttk.Button(self, text="Previous", command=lambda: self.move(-1)).grid(row=2, column=4)
        ttk.Button(self, text="Next", command=lambda: self.move(1)).grid(row=2, column=5)
        self.status = ttk.Label(self, text="")
        self.status.grid(row=2, column=6, columnspan=2)
        self.canvas.bind("<ButtonPress-1>", self.pointer_down)
        self.canvas.bind("<B1-Motion>", self.pointer_move)
        self.canvas.bind("<ButtonRelease-1>", self.pointer_up)
        self.show_current()

    def current(self) -> dict:
        return self.items[self.index]

    def _image(self, item: dict) -> Image.Image:
        source = self.sources.get(item["source_sha256"])
        if source is None:
            raise ValueError("A local source matching the anonymized holdout identifier was not found")
        capture = cv2.VideoCapture(str(source))
        capture.set(cv2.CAP_PROP_POS_FRAMES, item["source_frame"])
        ok, frame = capture.read()
        capture.release()
        if not ok:
            raise ValueError("The requested local holdout frame could not be read")
        return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    def show_current(self) -> None:
        item = self.current()
        self.original = self._image(item)
        self.scale = min(1000 / self.original.width, 620 / self.original.height)
        self.display_size = (int(self.original.width * self.scale), int(self.original.height * self.scale))
        review = self.reviews.get(item["id"])
        self.frozen = bool(review and review.get("approved") and review.get("review_status") == "approved_geometry")
        if review:
            # Compatibility is an in-memory view. Frozen approved rows retain
            # their original bbox/region bytes in ``self.reviews``.
            view = compatibility_view(review)
            self.components = view["components"]
            self.trust.set(view["frame_state"])
        else:
            # Blind mode: never seed a human review with model output.
            self.components = []
            self.trust.set("trusted")
        state = "disabled" if self.frozen else "normal"
        for control in (self.delete_button, self.region_button, self.save_button, self.approve_button):
            control.config(state=state)
        self.selected = None
        self.redraw()

    def redraw(self) -> None:
        counts = geometry_counts(self.components)
        self.hand_count.set(str(counts["expected_hand_region_count"]))
        self.draw_visual_count.set(str(counts["expected_draw_visual_count"]))
        self.concealed_count.set(str(counts["expected_concealed_tile_count"]))
        image = self.original.resize(self.display_size)
        draw = ImageDraw.Draw(image)
        for index, component in enumerate(self.components):
            x, y, width, height = component["pixel_bbox"]
            box = [int(x*self.scale), int(y*self.scale), int((x+width)*self.scale), int((y+height)*self.scale)]
            color = COLORS[component["region_candidate"]]
            draw.rectangle(box, outline=color, width=3 if index == self.selected else 2)
            draw.text((box[0], max(0, box[1]-14)), component["region_candidate"], fill=color)
        self.photo = ImageTk.PhotoImage(image)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        item = self.current()
        approved = sum(row.get("approved") and row.get("review_status") == "approved_geometry" for row in self.reviews.values())
        freeze_note = " [FROZEN]" if self.frozen else ""
        self.status.config(text=f"{self.index + 1}/{len(self.items)} | approved {approved}/{len(self.items)} | {item['id']}{freeze_note}")

    def pointer_down(self, event) -> None:
        if self.frozen:
            return
        x, y = event.x / self.scale, event.y / self.scale
        self.drag_start, self.selected = (x, y), None
        for index, component in enumerate(self.components):
            bx, by, bw, bh = component["pixel_bbox"]
            if bx <= x <= bx + bw and by <= y <= by + bh:
                self.selected = index
                break
        self.redraw()

    def pointer_move(self, event) -> None:
        if self.frozen or self.drag_start is None or self.selected is None:
            return
        x, y = event.x / self.scale, event.y / self.scale
        bx, by, bw, bh = self.components[self.selected]["pixel_bbox"]
        dx, dy = int(x - self.drag_start[0]), int(y - self.drag_start[1])
        self.components[self.selected]["pixel_bbox"] = [max(0, bx + dx), max(0, by + dy), bw, bh]
        self.drag_start = (x, y)
        self.redraw()

    def pointer_up(self, event) -> None:
        if self.frozen:
            return
        x, y = event.x / self.scale, event.y / self.scale
        if self.selected is None and self.drag_start:
            x0, y0 = self.drag_start
            box = [int(min(x0, x)), int(min(y0, y)), int(abs(x - x0)), int(abs(y - y0))]
            if box[2] > 4 and box[3] > 4:
                self.components.append({"pixel_bbox": box, "region_candidate": self.region.get(), "confidence": 1.0})
        self.drag_start = None
        self.redraw()
        self.save_draft()

    def row(self, approved: bool) -> dict:
        item = self.current()
        return {
            "id": item["id"], "source_id": item["source_id"], "source_session": item["source_session"],
            "source_frame": item["source_frame"], "source_sha256": item["source_sha256"], "size": item["size"],
            **new_geometry_row_fields(self.components, self.trust.get()),
            "review_status": "approved_geometry" if approved else "draft",
            "approved": approved, "reviewer": "manual_blind_holdout",
        }

    def save_draft(self) -> None:
        if self.frozen:
            return
        try:
            self.reviews[self.current()["id"]] = self.row(False)
        except ValueError:
            return
        save_rows(self.truth_path, self.reviews)
        self.redraw()

    def delete_selected(self) -> None:
        if self.frozen or self.selected is None:
            return
        self.components.pop(self.selected)
        self.selected = None
        self.save_draft()
        self.redraw()

    def apply_region(self) -> None:
        if self.frozen or self.selected is None:
            return
        self.components[self.selected]["region_candidate"] = self.region.get()
        self.save_draft()
        self.redraw()

    def approve_next(self) -> None:
        if self.frozen:
            return
        try:
            self.reviews[self.current()["id"]] = self.row(True)
        except ValueError as error:
            messagebox.showerror("Invalid geometry", str(error))
            return
        save_rows(self.truth_path, self.reviews)
        complete = all(
            self.reviews.get(item["id"], {}).get("approved")
            and self.reviews[item["id"]].get("review_status") == "approved_geometry"
            for item in self.items
        )
        self.move(1)
        if complete:
            from .geometry_holdout_metrics import evaluate
            report = evaluate(self.dataset, self.plan_path, self.truth_path, self.sources)
            messagebox.showinfo("Phase 5C metrics written", f"Holdout report written. Phase 6 allowed: {report['phase6_formal_tile_labeling_allowed']}")

    def move(self, delta: int) -> None:
        self.index = max(0, min(len(self.items) - 1, self.index + delta))
        self.show_current()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a blind, human-only Phase 5C holdout geometry review")
    parser.add_argument("--dataset", default="dataset/tiles_runtime_v0_2")
    parser.add_argument("--media-root", default="data/capture_validation")
    args = parser.parse_args()
    BlindHoldoutReview(Path(args.dataset), Path(args.media_root)).mainloop()


if __name__ == "__main__":
    main()
