"""Lock a fresh source-disjoint Runtime Vision V0.2 promotion batch.

This tool runs before detector/classifier evaluation. It:
- hashes local recordings;
- excludes every tracked development source token;
- deterministically locks source sessions and 20/50/80% frame positions;
- creates an anonymous lock manifest;
- creates metadata-only manual-truth skeletons;
- creates a promotion-bundle skeleton with all result metrics still null.

It never calls the detector/classifier and never fills manual truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2

from .phase5b_holdout import locate_sources
from .phase5e_holdout import (
    FRACTIONS,
    SOURCE_COUNT,
    _known_source_tokens,
    _source_is_known,
)


def _video_metadata(path: Path) -> tuple[int, int, int]:
    capture = cv2.VideoCapture(str(path))
    try:
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        capture.release()
    if width <= 0 or height <= 0 or frame_count <= 0:
        raise ValueError(f"Unreadable video metadata: {path}")
    return width, height, frame_count


def _batch_id(source_hashes: list[str]) -> str:
    payload = "|".join(source_hashes).encode("ascii")
    return "independent_" + hashlib.sha256(payload).hexdigest()[:16]


def _promotion_bundle(source_sessions: int) -> dict:
    return {
        "schema_version": "vision_runtime_v0_2_independent_bundle_v0_1",
        "provenance": {
            "independent_batch": True,
            "holdout_locked_before_evaluation": True,
            "tuning_after_lock": False,
            "source_sessions": source_sessions,
        },
        "geometry": {
            "component_precision": None,
            "component_recall": None,
            "hand_count_exact_match_rate": None,
            "runtime_region_errors": None,
        },
        "tile_identity": {
            "standard_classes_covered": None,
            "standard_classes_missing": None,
            "accepted_accuracy": None,
            "accepted_labels": None,
        },
        "draw_temporal": {
            "events": None,
            "precision": None,
            "recall": None,
            "duplicate_events": None,
        },
        "public_state": {
            "score_points": None,
            "score_pair_accuracy": None,
            "status_points": None,
            "remaining_tiles_accuracy": None,
            "hand_index_accuracy": None,
        },
        "gold": {
            "sessions": None,
            "session_majority_accuracy": None,
        },
        "stress": {
            "cases": None,
            "unsafe_acceptances": None,
        },
        "policy": {
            "safe_for_executor": False,
        },
    }


def _truth_skeleton(frame: dict) -> dict:
    return {
        "id": frame["id"],
        "source_id": frame["source_id"],
        "source_session": frame["source_session"],
        "source_sha256": frame["source_sha256"],
        "source_frame": frame["source_frame"],
        "size": frame["size"],
        "selection_role": frame["selection_role"],
        "manual_truth_required": True,
        "frame_state": None,
        "animation_type": None,
        "scene_type": None,
        "components": None,
        "review_status": "unreviewed_holdout",
        "approved": False,
        "reviewer": None,
    }


def build_lock(
    root: Path,
    dataset: Path,
    output_root: Path,
    *,
    source_count: int = SOURCE_COUNT,
) -> dict:
    if source_count < SOURCE_COUNT:
        raise ValueError(
            f"Independent promotion batch requires at least {SOURCE_COUNT} source sessions"
        )

    known_tokens = _known_source_tokens(dataset)
    located = locate_sources(root)
    candidates = []
    rejected_known = []

    for source_hash, path in sorted(located.items()):
        if _source_is_known(source_hash, known_tokens):
            rejected_known.append("src_" + source_hash[:16])
            continue
        width, height, frame_count = _video_metadata(path)
        if frame_count < 120:
            continue
        candidates.append((source_hash, width, height, frame_count))

    if len(candidates) < source_count:
        raise ValueError(
            "Not enough fresh source-disjoint recordings: "
            f"need {source_count}, found {len(candidates)}"
        )

    selected = candidates[:source_count]
    hashes = [row[0] for row in selected]
    batch_id = _batch_id(hashes)
    batch_dir = output_root / batch_id
    lock_path = batch_dir / "batch_lock.json"
    truth_path = batch_dir / "geometry_truth.blank.jsonl"
    bundle_path = batch_dir / "promotion_bundle.blank.json"

    for path in (lock_path, truth_path, bundle_path):
        if path.exists():
            raise FileExistsError(
                f"Refusing to overwrite an existing blind-batch artifact: {path}"
            )

    sources = []
    frames = []
    for source_hash, width, height, frame_count in selected:
        source_id = "src_" + source_hash[:16]
        session_id = "session_" + source_hash[:16]
        sources.append({
            "source_id": source_id,
            "source_session": session_id,
            "source_sha256": source_hash,
            "size": [width, height],
            "frame_count": frame_count,
        })
        for fraction in FRACTIONS:
            source_frame = int(round((frame_count - 1) * fraction))
            frames.append({
                "id": f"{batch_id}_{len(frames) + 1:04d}",
                "source_id": source_id,
                "source_session": session_id,
                "source_sha256": source_hash,
                "source_frame": source_frame,
                "size": [width, height],
                "selection_role": (
                    f"detector_blind_fraction_{int(fraction * 100)}"
                ),
                "review_status": "unreviewed_holdout",
                "approved": False,
            })

    lock = {
        "schema_version": "vision_runtime_v0_2_independent_batch_lock_v0_1",
        "batch_id": batch_id,
        "status": "locked_before_evaluation",
        "selection_lock": (
            "Source hashes and 20/50/80 percent frame positions were frozen before "
            "detector/classifier evaluation. Do not tune on this batch. If the batch "
            "is revealed during debugging, collect a new untouched batch for the next "
            "formal promotion attempt."
        ),
        "source_disjoint_policy": (
            "Reject any candidate whose full hash equals or begins with a tracked "
            "geometry/approved-label source token. Conservative over-exclusion is "
            "allowed."
        ),
        "known_source_token_count": len(known_tokens),
        "rejected_known_sources": rejected_known,
        "independent_batch": True,
        "holdout_locked_before_evaluation": True,
        "tuning_after_lock": False,
        "selected_session_count": len(sources),
        "selected_frame_count": len(frames),
        "sources": sources,
        "frames": frames,
        "manual_truth_file": truth_path.name,
        "promotion_bundle_file": bundle_path.name,
        "safe_for_executor": False,
        "privacy": (
            "Persisted artifacts contain content hashes and geometry only; local "
            "paths and filenames are not written."
        ),
    }

    batch_dir.mkdir(parents=True, exist_ok=False)
    lock_path.write_text(
        json.dumps(lock, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    truth_path.write_text(
        "".join(
            json.dumps(_truth_skeleton(frame), ensure_ascii=False) + "\n"
            for frame in frames
        ),
        encoding="utf-8",
    )
    bundle_path.write_text(
        json.dumps(
            _promotion_bundle(len(sources)),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return lock


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lock a fresh source-disjoint Runtime Vision V0.2 batch"
    )
    parser.add_argument(
        "--root",
        required=True,
        help="Local directory containing only intended fresh recording candidates",
    )
    parser.add_argument(
        "--dataset",
        default="dataset/tiles_runtime_v0_2",
    )
    parser.add_argument(
        "--output-root",
        default="data/vision_independent_batches",
    )
    parser.add_argument(
        "--source-count",
        type=int,
        default=SOURCE_COUNT,
    )
    args = parser.parse_args()
    result = build_lock(
        Path(args.root),
        Path(args.dataset),
        Path(args.output_root),
        source_count=args.source_count,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
