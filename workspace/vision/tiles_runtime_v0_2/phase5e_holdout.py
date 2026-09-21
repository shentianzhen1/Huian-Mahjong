"""Build a detector-blind, source-disjoint Phase 5E geometry holdout."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

from .phase5b_holdout import locate_sources


FRACTIONS = (0.20, 0.50, 0.80)
SOURCE_COUNT = 8


def _anonymous_token(value: str | None, prefix: str) -> str | None:
    if not value or not value.startswith(prefix):
        return None
    token = value[len(prefix):].strip().lower()
    return token or None


def _known_source_tokens(dataset: Path) -> set[str]:
    """Collect conservative source identifiers from every tracked evidence family.

    Full source hashes from geometry truth are preferred. Approved tile labels do
    not expose the raw media hash, so their anonymized source/session suffixes
    are also treated as exclusion prefixes. This can over-exclude a candidate,
    which is acceptable for a blind promotion holdout; it must never under-
    exclude a known development source.
    """
    tokens: set[str] = set()
    truth_paths = [
        dataset / "validation" / "geometry_ground_truth_v0_2.jsonl",
        dataset / "validation" / "holdout" / "geometry_holdout_ground_truth_v0_2.jsonl",
    ]
    for path in truth_paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            row = json.loads(line)
            source_hash = row.get("source_sha256")
            if source_hash:
                tokens.add(str(source_hash).lower())
            for field, prefix in (("source_id", "src_"), ("source_session", "session_")):
                token = _anonymous_token(row.get(field), prefix)
                if token:
                    tokens.add(token)

    labels_path = dataset / "labels.jsonl"
    if labels_path.exists():
        for line in labels_path.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            row = json.loads(line)
            if not row.get("approved"):
                continue
            for field, prefix in (("source_id", "src_"), ("source_session", "session_")):
                token = _anonymous_token(row.get(field), prefix)
                if token:
                    tokens.add(token)
    return tokens


def _source_is_known(source_hash: str, known_tokens: set[str]) -> bool:
    source_hash = source_hash.lower()
    return any(source_hash == token or source_hash.startswith(token) for token in known_tokens)


def build(root: Path, dataset: Path, output: Path) -> dict:
    known_tokens = _known_source_tokens(dataset)
    sources = locate_sources(root)
    candidates = []
    for source_hash, source in sorted(sources.items()):
        if _source_is_known(source_hash, known_tokens):
            continue
        capture = cv2.VideoCapture(str(source))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        capture.release()
        if frame_count >= 120:
            candidates.append((source_hash, width, height, frame_count))
    selected = candidates[:SOURCE_COUNT]
    if len(selected) < SOURCE_COUNT:
        raise ValueError("Not enough source-disjoint local recordings for Phase 5E")

    frames = []
    for source_hash, width, height, frame_count in selected:
        for fraction in FRACTIONS:
            frame = int(round((frame_count - 1) * fraction))
            frames.append({
                "id": f"phase5e_holdout_{len(frames) + 1:04d}",
                "source_id": "src_" + source_hash[:16],
                "source_session": "session_" + source_hash[:16],
                "source_sha256": source_hash,
                "source_frame": frame,
                "size": [width, height],
                "selection_role": f"detector_blind_fraction_{int(fraction * 100)}",
                "review_status": "unreviewed_holdout",
                "approved": False,
            })
    resolutions = {}
    for row in frames:
        key = f"{row['size'][0]}x{row['size'][1]}"
        resolutions[key] = resolutions.get(key, 0) + 1
    plan = {
        "schema_version": "vision_runtime_v0_2_phase5e_blind_holdout",
        "status": "awaiting_independent_manual_geometry_review",
        "selection_lock": (
            "Selected from source sessions absent from all tracked geometry truth and "
            "approved runtime tile-label source/session identifiers. Frames use fixed "
            "20/50/80 percent positions; the detector was not called. Do not tune on "
            "these frames after selection."
        ),
        "source_disjoint_policy": (
            "Reject a candidate when its full source hash equals or begins with any "
            "tracked full hash or anonymized src_/session_ suffix from geometry truth "
            "or approved Runtime V0.2 labels. Conservative over-exclusion is allowed."
        ),
        "known_source_token_count": len(known_tokens),
        "source_disjoint_from_tracked_evidence": True,
        "privacy": "Only anonymous content hashes and frame geometry are tracked.",
        "frames": frames,
        "selected_frame_count": len(frames),
        "selected_session_count": len(selected),
        "resolution_counts": resolutions,
        "coverage_review_required": [
            "stable versus animation/non_game",
            "hand/draw_visual/meld/public-gold geometry",
            "stacked 3+1 meld when present",
            "960x448 independent-session evidence",
        ],
        "phase6_formal_tile_labeling_allowed": False,
        "safe_for_executor": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return plan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="data/capture_validation")
    parser.add_argument("--dataset", default="dataset/tiles_runtime_v0_2")
    parser.add_argument(
        "--output",
        default="dataset/tiles_runtime_v0_2/validation/holdout/phase5e_geometry_holdout_plan_v0_2.json",
    )
    args = parser.parse_args()
    print(json.dumps(
        build(Path(args.root), Path(args.dataset), Path(args.output)),
        ensure_ascii=False, indent=2,
    ))


if __name__ == "__main__":
    main()
