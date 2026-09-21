"""Create the source-disjoint, anonymous Phase 5B geometry holdout plan.

The plan stores content-derived source identifiers, not file paths, filenames,
or screenshots.  It is a review queue only: no detector output is persisted as
truth and no selected frame may subsequently be used for detector tuning.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2


# Content SHA-256 values identify local sources without exposing their names or
# paths in the checked-in plan.  These eight sources are disjoint from all
# Phase 5 approved-review videos and from the two Phase 5B tuning windows.
HOLDOUT_SPECS = (
    ("dcac8580c55879a2e12d64961caa84a2ac7fb009b422691381a3eac24e661d6a", ((60, "opening_or_17_hand_candidate"), (120, "draw_candidate"), (360, "visible_meld_candidate"))),
    ("4d68a8e72498d7290411e97f806913733b376dd880cbb87b02b711482a68e4fe", ((120, "opening_or_17_hand_candidate"), (420, "visible_meld_candidate"), (540, "draw_and_meld_candidate"))),
    ("781bfe34c40993effb0bb76b5d576f9c3df400784bbd1ed8820dc0c8aacdba82", ((0, "opening_or_17_hand_candidate"), (300, "draw_candidate"), (840, "visible_meld_candidate"))),
    ("627b6c2022d3f910b3e2d258360440ccb17d3fb515cc0982c6f74a3b99409bed", ((60, "opening_or_17_hand_candidate"), (180, "draw_candidate"), (720, "visible_meld_candidate"))),
    ("5e02f7d0458be0a923231d87921b5506ce4e15d1412bb560d59b5e61f7eb2c39", ((0, "opening_or_17_hand_candidate"), (60, "draw_candidate"), (180, "opening_or_17_hand_candidate"))),
    ("0e565528164aa77faf5916f50b98678829a8987c29fb0181e49505ad7269179f", ((0, "opening_or_17_hand_candidate"), (60, "draw_candidate"), (120, "opening_or_17_hand_candidate"))),
    ("94960e642f407502278c66c8f954f062c58f3f43b5d6ce545d8c938efdd32919", ((0, "opening_or_17_hand_candidate"), (240, "draw_and_meld_candidate"), (300, "gold_candidate"))),
    ("59460988023cc9f105d119597218f5a8b0d7814352ab5889d8525d8a2b6d6135", ((0, "gold_and_meld_candidate"), (60, "gold_and_meld_candidate"), (90, "transition_or_rejection_candidate"))),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def locate_sources(root: Path) -> dict[str, Path]:
    sources = {}
    for path in root.rglob("*"):
        if path.suffix.lower() in {".avi", ".mp4", ".mov", ".mkv"}:
            sources[sha256(path)] = path
    return sources


def build(root: Path, output: Path) -> dict:
    sources = locate_sources(root)
    rows, missing = [], []
    for source_hash, samples in HOLDOUT_SPECS:
        source = sources.get(source_hash)
        if source is None:
            missing.append("src_" + source_hash[:16])
            continue
        capture = cv2.VideoCapture(str(source))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        capture.release()
        for frame, role in samples:
            if frame >= frame_count:
                raise ValueError(f"Holdout frame {frame} is outside the local source")
            rows.append({
                "id": f"phase5b_holdout_{len(rows) + 1:04d}",
                "source_id": "src_" + source_hash[:16],
                "source_session": "session_" + source_hash[:16],
                "source_sha256": source_hash,
                "source_frame": frame,
                "size": [width, height],
                "selection_role": role,
                "review_status": "unreviewed_holdout",
                "approved": False,
            })
    report = {
        "schema_version": "vision_runtime_v0_2_phase5b_holdout",
        "status": "awaiting_independent_manual_geometry_review",
        "selection_lock": "Source-disjoint from the 29 approved Phase 5 rows and excluded from Phase 5B detector tuning. Do not tune on these frames after selection.",
        "privacy": "Only content-derived anonymous source identifiers are stored. No local paths, filenames, full screenshots, player UI, names, or room identifiers are included.",
        "frames": rows,
        "selected_frame_count": len(rows),
        "selected_session_count": len({row["source_session"] for row in rows}),
        "resolutions": sorted({"%sx%s" % tuple(row["size"]) for row in rows}),
        "coverage_targets": {
            "second_960x448_session": "not_found_locally; a short new capture is required",
            "17_hand": "candidate_only; independent manual count is required before claiming coverage",
            "meld": "candidate_frames_selected",
            "draw_visual": "candidate_frames_selected",
            "gold_different_positions": "candidate_frames_selected; manual review required",
        },
        "missing_local_sources": missing,
        "safe_for_executor": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the anonymous Phase 5B geometry holdout plan")
    parser.add_argument("--root", default="data/capture_validation")
    parser.add_argument("--output", default="dataset/tiles_runtime_v0_2/validation/holdout/phase5b_geometry_holdout_plan_v0_2.json")
    args = parser.parse_args()
    print(json.dumps(build(Path(args.root), Path(args.output)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
