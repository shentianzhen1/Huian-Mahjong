"""Small local Tk review UI for approved V0.2 geometry ground truth."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageTk
import tkinter as tk
from tkinter import ttk

from .dynamic_geometry import detect_dynamic_geometry
from .geometry_schema import compatibility_view, geometry_counts, new_geometry_row_fields


SOURCE_REGISTRY = {
    "session_9aa2041d": "data/capture_validation/review_66fe863f_20260915/source.mp4",
    "session_7f4c1b2e": "data/capture_validation/review_b3892b34_20260915/source.mp4",
    "session_5d8a0e3c": "data/capture_validation/review_a562bd21_20260915/source.mp4",
}
SOURCE_IDS = {
    "session_9aa2041d": "src_66fe863f_local",
    "session_7f4c1b2e": "src_ac27bc0798ed252f",
    "session_5d8a0e3c": "src_04bf012ce76304b7",
}
COLORS = {
    "hand": "#38e878", "draw_visual": "#ff9f1c", "gold": "#ffd60a",
    "meld": "#64d2ff", "unknown": "#ff453a",
}


def candidates(report_path: Path) -> list[dict]:
    data = json.loads(report_path.read_text(encoding="utf-8"))
    rows = []
    for window in data["candidate_review_plan"]["planned_windows"]:
        for frame in window["frames"]:
            rows.append({
                "id": f"geo_{len(rows) + 1:04d}", "source_session": window["source_session"],
                "source_frame": frame, "size": window["size"], "candidate_state": window["state"],
            })
    return rows


def load_reviews(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    return {row["id"]: row for row in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)}


def save_reviews(path: Path, reviews: dict[str, dict]) -> None:
    """Durably replace the anonymized review file after every edit."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text("".join(json.dumps(reviews[key], ensure_ascii=False) + "\n" for key in sorted(reviews)), encoding="utf-8")
    temporary.replace(path)


def read_frame(session: str, frame_number: int) -> Image.Image:
    source = SOURCE_REGISTRY[session]
    capture = cv2.VideoCapture(source)
    capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    ok, frame = capture.read()
    capture.release()
    if not ok:
        raise ValueError(f"Cannot read local source frame for {session}:{frame_number}")
    return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))


class ReviewApp(tk.Tk):
    def __init__(self, dataset: Path):
        super().__init__()
        self.dataset = dataset
        self.report_path = dataset / "validation" / "reports" / "phase5_real_geometry_validation_v0_2.json"
        self.truth_path = dataset / "validation" / "geometry_ground_truth_v0_2.jsonl"
        self.items, self.reviews, self.index = candidates(self.report_path), load_reviews(self.truth_path), 0
        self.components, self.selected, self.drag_start = [], None, None
        self.frozen = False
        self.region, self.trust = tk.StringVar(value="hand"), tk.StringVar(value="trusted")
        self.hand_count, self.draw_visual_count, self.concealed_count = tk.StringVar(value="0"), tk.StringVar(value="0"), tk.StringVar(value="0")
        self.title("Huian Vision V0.2 Geometry Review")
        self.canvas = tk.Canvas(self, width=1000, height=520, background="black")
        self.canvas.grid(row=0, column=0, columnspan=8)
        ttk.Label(self, text="Region").grid(row=1, column=0)
        region_box = ttk.Combobox(self, textvariable=self.region, values=("hand", "draw_visual", "gold", "meld", "unknown"), width=12); region_box.grid(row=1, column=1)
        ttk.Label(self, text="Frame state").grid(row=1, column=2)
        trust_box = ttk.Combobox(self, textvariable=self.trust, values=("trusted", "occluded", "animation"), width=10); trust_box.grid(row=1, column=3)
        ttk.Label(self, text="hand / draw_visual / concealed").grid(row=1, column=4)
        ttk.Label(self, textvariable=self.hand_count).grid(row=1, column=5)
        ttk.Label(self, textvariable=self.draw_visual_count).grid(row=1, column=6)
        ttk.Label(self, textvariable=self.concealed_count).grid(row=1, column=7)
        for control in (region_box, trust_box):
            control.bind("<FocusOut>", lambda _event: self.save_draft())
        for control in (region_box, trust_box):
            control.bind("<<ComboboxSelected>>", lambda _event: self.save_draft())
        self.accept_button = ttk.Button(self, text="Accept whole frame", command=self.accept_whole); self.accept_button.grid(row=2, column=0)
        self.delete_button = ttk.Button(self, text="Delete selected", command=self.delete_selected); self.delete_button.grid(row=2, column=1)
        self.apply_button = ttk.Button(self, text="Apply region", command=self.apply_region); self.apply_button.grid(row=2, column=2)
        self.save_button = ttk.Button(self, text="Save draft", command=self.save_draft); self.save_button.grid(row=2, column=3)
        self.approve_button = ttk.Button(self, text="Approve & Next", command=self.approve_next); self.approve_button.grid(row=2, column=4)
        ttk.Button(self, text="Previous", command=lambda: self.move(-1)).grid(row=2, column=5)
        ttk.Button(self, text="Next", command=lambda: self.move(1)).grid(row=2, column=6)
        self.status = ttk.Label(self, text="")
        self.status.grid(row=2, column=7)
        self.canvas.bind("<ButtonPress-1>", self.pointer_down)
        self.canvas.bind("<B1-Motion>", self.pointer_move)
        self.canvas.bind("<ButtonRelease-1>", self.pointer_up)
        self.show_current()

    def current(self) -> dict:
        return self.items[self.index]

    def show_current(self) -> None:
        item = self.current(); image = read_frame(item["source_session"], item["source_frame"])
        self.original = image; self.scale = min(1000 / image.width, 520 / image.height)
        self.display_size = (int(image.width * self.scale), int(image.height * self.scale))
        review = self.reviews.get(item["id"])
        self.frozen = bool(review and review.get("approved") and review.get("review_status") == "approved_geometry")
        if review:
            view = compatibility_view(review)
            self.components = view["components"]; self.trust.set(view["frame_state"])
        else:
            observation = detect_dynamic_geometry(image, frame=item["source_frame"], session=item["source_session"])
            self.components = [{"pixel_bbox": list(component.pixel_bbox), "region_candidate": component.region_candidate, "confidence": component.confidence} for component in observation.components]
            self.trust.set("occluded" if observation.geometry_untrusted else "trusted")
        self._set_editable(not self.frozen)
        self.selected = None; self.redraw()

    def _set_editable(self, editable: bool) -> None:
        state = "normal" if editable else "disabled"
        for control in (
            self.accept_button, self.delete_button, self.apply_button,
            self.save_button, self.approve_button,
        ):
            control.config(state=state)

    def redraw(self) -> None:
        counts = geometry_counts(self.components)
        self.hand_count.set(str(counts["expected_hand_region_count"]))
        self.draw_visual_count.set(str(counts["expected_draw_visual_count"]))
        self.concealed_count.set(str(counts["expected_concealed_tile_count"]))
        image = self.original.resize(self.display_size)
        draw = ImageDraw.Draw(image)
        for index, component in enumerate(self.components):
            x, y, width, height = component["pixel_bbox"]; box = [int(x*self.scale), int(y*self.scale), int((x+width)*self.scale), int((y+height)*self.scale)]
            color = COLORS[component["region_candidate"]]; draw.rectangle(box, outline=color, width=3 if index == self.selected else 2)
            draw.text((box[0], max(0, box[1]-14)), f"{component['region_candidate']} {component.get('confidence', 1):.2f}", fill=color)
        self.photo = ImageTk.PhotoImage(image); self.canvas.delete("all"); self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        item = self.current(); freeze_note = " [FROZEN]" if self.frozen else ""
        self.status.config(text=f"{self.index+1}/{len(self.items)} {item['id']} {item['source_session']}:{item['source_frame']}{freeze_note}")

    def pointer_down(self, event) -> None:
        if self.frozen: return
        x, y = event.x/self.scale, event.y/self.scale; self.drag_start = (x, y); self.selected = None
        for index, component in enumerate(self.components):
            bx, by, bw, bh = component["pixel_bbox"]
            if bx <= x <= bx+bw and by <= y <= by+bh: self.selected = index; break
        self.redraw()

    def pointer_move(self, event) -> None:
        if self.frozen: return
        if self.drag_start is None: return
        x, y = event.x/self.scale, event.y/self.scale
        if self.selected is not None:
            bx, by, bw, bh = self.components[self.selected]["pixel_bbox"]
            dx, dy = int(x-self.drag_start[0]), int(y-self.drag_start[1]); self.components[self.selected]["pixel_bbox"] = [max(0,bx+dx), max(0,by+dy), bw, bh]; self.drag_start = (x,y)
        self.redraw()

    def pointer_up(self, event) -> None:
        if self.frozen: return
        x, y = event.x/self.scale, event.y/self.scale
        if self.selected is None and self.drag_start:
            x0, y0 = self.drag_start; box = [int(min(x0,x)), int(min(y0,y)), int(abs(x-x0)), int(abs(y-y0))]
            if box[2] > 4 and box[3] > 4: self.components.append({"pixel_bbox": box, "region_candidate": self.region.get(), "confidence": 1.0})
        self.drag_start = None; self.redraw(); self.save_draft()

    def delete_selected(self) -> None:
        if self.frozen: return
        if self.selected is not None: self.components.pop(self.selected); self.selected = None; self.save_draft(); self.redraw()

    def apply_region(self) -> None:
        if self.frozen: return
        if self.selected is not None: self.components[self.selected]["region_candidate"] = self.region.get(); self.save_draft(); self.redraw()

    def row(self, approved: bool) -> dict:
        item = self.current()
        return {"id": item["id"], "source_id": SOURCE_IDS[item["source_session"]], "source_session": item["source_session"], "source_frame": item["source_frame"], "size": item["size"], **new_geometry_row_fields(self.components, self.trust.get()), "review_status": "approved_geometry" if approved else "draft", "approved": approved, "reviewer": "manual"}

    def save_draft(self) -> None:
        if self.frozen: return
        self.reviews[self.current()["id"]] = self.row(False); save_reviews(self.truth_path, self.reviews)

    def accept_whole(self) -> None:
        if self.frozen: return
        self.trust.set("trusted"); self.save_draft(); self.redraw()

    def approve_next(self) -> None:
        if self.frozen: return
        self.reviews[self.current()["id"]] = self.row(True); save_reviews(self.truth_path, self.reviews); self.move(1)
        if len([row for row in self.reviews.values() if row.get("approved")]) == len(self.items):
            from .geometry_metrics import evaluate
            evaluate(self.dataset)

    def move(self, delta: int) -> None:
        self.index = max(0, min(len(self.items)-1, self.index+delta)); self.show_current()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="dataset/tiles_runtime_v0_2")
    args = parser.parse_args(); ReviewApp(Path(args.dataset)).mainloop()


if __name__ == "__main__":
    main()
