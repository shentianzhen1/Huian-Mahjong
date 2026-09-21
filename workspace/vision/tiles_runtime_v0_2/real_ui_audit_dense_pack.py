"""Create dense, local-only frame strips for selected Real UI audit windows.

The output lives below the ignored dataset ``work/`` tree.  It is intended for
human observation of UI ordering; it does not run Dynamic Geometry and does not
change detector rules.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageFont


DEFAULT_IDS = (
    "ui_audit_0035",
    "ui_audit_0047",
    "ui_audit_0051",
    "ui_audit_0060",
    "ui_audit_0062",
    "ui_audit_0117",
    "ui_audit_0036",
    "ui_audit_0061",
    "ui_audit_0078",
    "ui_audit_0148",
    "ui_audit_0155",
    "ui_audit_0164",
    "ui_audit_0176",
    "ui_audit_0145",
)


def _load_rows(manifest: Path) -> dict[str, dict]:
    return {
        row["id"]: row
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line and (row := json.loads(line))
    }


def _frame(cap: cv2.VideoCapture, frame_index: int) -> Image.Image | None:
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, bgr = cap.read()
    if not ok:
        return None
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def build(repo: Path, ids: list[str], interval_seconds: float = 0.2) -> dict:
    work = repo / "dataset" / "tiles_runtime_v0_2" / "work" / "real_ui_behavior_audit_v0_1"
    rows = _load_rows(work / "candidate_windows.jsonl")
    output = work / "dense_review"
    output.mkdir(parents=True, exist_ok=True)
    result_rows = []

    for candidate_id in ids:
        row = rows[candidate_id]
        video = repo / row["relative_source_path"]
        cap = cv2.VideoCapture(str(video))
        fps = float(cap.get(cv2.CAP_PROP_FPS) or row["fps"] or 10.0)
        step = max(1, round(fps * interval_seconds))
        start, end = row["frame_range"]
        indices = list(range(start, end + 1, step))
        if indices[-1] != end:
            indices.append(end)

        frames = []
        for frame_index in indices:
            image = _frame(cap, frame_index)
            if image is not None:
                frames.append((frame_index, image))
        cap.release()
        if not frames:
            continue

        thumb_width = 360
        scale = thumb_width / frames[0][1].width
        thumb_height = round(frames[0][1].height * scale)
        columns = 4
        rows_count = (len(frames) + columns - 1) // columns
        header_height = 38
        cell_height = thumb_height + 24
        canvas = Image.new("RGB", (columns * thumb_width, header_height + rows_count * cell_height), "white")
        draw = ImageDraw.Draw(canvas)
        draw.text(
            (8, 7),
            f"{candidate_id} | {row['source_session']} | {start}-{end} | every {step} frame(s)",
            fill="black",
        )
        for index, (frame_index, image) in enumerate(frames):
            x = (index % columns) * thumb_width
            y = header_height + (index // columns) * cell_height
            thumb = image.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)
            canvas.paste(thumb, (x, y))
            draw.text((x + 5, y + thumb_height + 3), f"frame {frame_index} | {frame_index / fps:.2f}s", fill="black")

        target = output / f"{candidate_id}_dense.jpg"
        canvas.save(target, quality=92)
        result_rows.append(
            {
                "id": candidate_id,
                "source_session": row["source_session"],
                "frame_range": row["frame_range"],
                "sampled_frames": [item[0] for item in frames],
                "file": target.relative_to(work).as_posix(),
            }
        )

    index = {
        "schema_version": "real_ui_behavior_audit_dense_review_v0_1",
        "detector_invoked": False,
        "purpose": "Human observation of temporal UI ordering only.",
        "items": result_rows,
    }
    (output / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return index


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--ids", nargs="*", default=list(DEFAULT_IDS))
    parser.add_argument("--interval-seconds", type=float, default=0.2)
    args = parser.parse_args()
    result = build(args.repo.resolve(), args.ids, args.interval_seconds)
    print(json.dumps({"items": len(result["items"]), "detector_invoked": False}, indent=2))


if __name__ == "__main__":
    main()
