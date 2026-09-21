"""Build a compact local review pack from automatic UI audit candidates."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw


TARGET_TYPES = (
    "settlement_template_candidate",
    "right_independent_tile_appeared",
    "right_independent_tile_disappeared",
    "hand_count_increase",
    "hand_count_decrease",
    "meld_count_increase",
    "meld_count_decrease",
    "gold_count_increase",
    "gold_count_decrease",
    "action_button_or_right_ui_change",
    "large_scene_or_overlay_transition",
    "bottom_layout_motion",
    "centre_discard_or_action_motion",
)


def _score(row: dict) -> float:
    motion = row["motion"]
    return motion["global"] + motion["bottom"] + motion["centre"] + motion["right_ui"]


def build(dataset: Path) -> dict:
    work = dataset / "work" / "real_ui_behavior_audit_v0_1"
    manifest = work / "candidate_windows.jsonl"
    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines() if line]
    selected: dict[str, dict] = {}
    coverage: dict[str, list[str]] = defaultdict(list)

    for candidate_type in TARGET_TYPES:
        candidates = sorted(
            (row for row in rows if candidate_type in row["candidate_types"]),
            key=_score,
            reverse=True,
        )
        sessions: set[str] = set()
        for row in candidates:
            if row["source_session"] in sessions:
                continue
            selected[row["id"]] = row
            coverage[candidate_type].append(row["id"])
            sessions.add(row["source_session"])
            if len(sessions) >= 4:
                break

    # Preserve several globally strongest complete-game transitions even if
    # their heuristic types duplicate the stratified choices.
    for row in sorted((row for row in rows if row["full_game_set"]), key=_score, reverse=True)[:8]:
        selected[row["id"]] = row

    shortlist = sorted(selected.values(), key=lambda row: (row["source_session"], row["peak_frame"]))
    shortlist_path = work / "review_shortlist.jsonl"
    shortlist_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in shortlist),
        encoding="utf-8",
    )

    page_dir = work / "review_pages"
    page_dir.mkdir(parents=True, exist_ok=True)
    page_files = []
    rows_per_page = 4
    for page_index in range(0, len(shortlist), rows_per_page):
        page_rows = shortlist[page_index:page_index + rows_per_page]
        canvas = Image.new("RGB", (1200, len(page_rows) * 215), "white")
        draw = ImageDraw.Draw(canvas)
        for row_index, row in enumerate(page_rows):
            top = row_index * 215
            header = (
                f"{row['id']} | {row['source_session']} | frames {row['frame_range'][0]}-{row['frame_range'][1]} | "
                + ", ".join(row["candidate_types"])
            )
            draw.text((5, top + 3), header[:185], fill="black")
            sheet = Image.open(work / row["contact_sheet"]).convert("RGB")
            canvas.paste(sheet, (0, top + 35))
        page_path = page_dir / f"page_{page_index // rows_per_page + 1:02d}.jpg"
        canvas.save(page_path, quality=90)
        page_files.append(page_path.relative_to(work).as_posix())

    index = {
        "schema_version": "real_ui_behavior_audit_review_pack_v0_1",
        "candidate_count": len(rows),
        "shortlist_count": len(shortlist),
        "selection": "Up to four source-distinct examples per heuristic type plus eight strongest full-game transitions.",
        "coverage": dict(coverage),
        "review_pages": page_files,
        "human_confirmation_required": True,
    }
    (work / "review_pack_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return index


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="dataset/tiles_runtime_v0_2")
    args = parser.parse_args()
    print(json.dumps(build(Path(args.dataset)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
