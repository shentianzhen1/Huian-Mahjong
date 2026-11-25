"""Private exact-source regression for the reviewed round-6 3 -> 4 meld event.

This runner is development-only and intentionally source-specific. It verifies
an exact private video SHA, decodes only frozen reviewed frames, selects the
reviewed lower meld group by target coverage, and runs:

public detector -> meld normalization/bridge -> MeldSnapshotObserver ->
PublicReplayCandidate -> issue69 temporal reconstruction.

The private output may contain exact source identifiers and must not be
committed. Nothing here changes Runtime, Hint, Rules, AI, or Executor.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from workspace.vision.issue69_public_replay_adapters import meld_observation_candidate
from workspace.vision.issue69_temporal_reconstruction import reconstruct_public_candidates
from workspace.vision.public_meld_structure_snapshot_bridge import (
    review_public_meld_structure_snapshot,
)
from workspace.vision.public_observers import MeldSnapshotObserver
from workspace.vision.public_tile_detector import (
    best_target_coverage,
    detect_public_tile_geometry,
)

_SHA = re.compile(r"^[a-f0-9]{64}$")
FRAME_SIZE = (1108, 512)
FLAT_FRAMES = (3309, 3312, 3315, 3318, 3321)
STACKED_FRAMES = (3351, 3354, 3357, 3360, 3363)
FLAT_TARGET = (
    99 / FRAME_SIZE[0], 429 / FRAME_SIZE[1],
    140 / FRAME_SIZE[0], 78 / FRAME_SIZE[1],
)
STACKED_TARGET = (
    99 / FRAME_SIZE[0], 416 / FRAME_SIZE[1],
    140 / FRAME_SIZE[0], 91 / FRAME_SIZE[1],
)
MIN_TARGET_COVERAGE = 0.80


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def replay_round6_meld_upgrade(
    video_path: str | Path,
    *,
    source_session: str,
    expected_sha256: str,
) -> dict:
    import cv2
    from PIL import Image

    video = Path(video_path)
    if not source_session:
        raise ValueError("source_session required")
    if not _SHA.fullmatch(expected_sha256):
        raise ValueError("exact expected SHA256 required")
    actual_sha = _sha256(video)
    if actual_sha != expected_sha256:
        raise ValueError("video SHA256 mismatch")

    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise ValueError("video cannot be decoded")
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    if (width, height) != FRAME_SIZE:
        capture.release()
        raise ValueError("source resolution does not match reviewed round-6 source")
    if fps <= 0:
        capture.release()
        raise ValueError("invalid source FPS")

    observer = MeldSnapshotObserver(settle_frames=5)
    trace = []
    emitted = None
    try:
        for frame_index in (*FLAT_FRAMES, *STACKED_FRAMES):
            if not capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index):
                raise ValueError(f"failed to seek frame {frame_index}")
            ok, bgr = capture.read()
            if not ok:
                raise ValueError(f"missing source frame {frame_index}")
            pts = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            image = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
            detection = detect_public_tile_geometry(
                image, frame=frame_index, session=source_session,
            )
            target = FLAT_TARGET if frame_index in FLAT_FRAMES else STACKED_TARGET
            score, group = best_target_coverage(detection, target)
            if group is None or group.geometry_kind != "bottom_group" or score < MIN_TARGET_COVERAGE:
                raise ValueError(
                    f"reviewed meld group not recovered at frame {frame_index}: coverage={score:.6f}"
                )
            review = review_public_meld_structure_snapshot(
                image,
                group,
                timestamp_seconds=pts,
                actor="player",
                source_session=source_session,
                stream_epoch=0,
                frame_index=frame_index,
                source_frame_verified=True,
                public_meld_region_verified=True,
                evidence_refs=(f"round6-reviewed-meld:frame:{frame_index}",),
            )
            observed = observer.observe(review.snapshot)
            trace.append({
                "frame_index": frame_index,
                "timestamp_seconds": round(pts, 6),
                "target_coverage": round(score, 6),
                "group_bbox": list(group.pixel_bbox),
                "stack_state": review.geometry.stack_state,
                "structural_face_count": review.structural_face_count,
                "observer_stable": observed.stable,
                "observer_trusted": observed.trusted,
                "observer_issues": list(observed.issues),
            })
            if observed.observation is not None:
                if emitted is not None:
                    raise ValueError("expected exactly one meld delta")
                emitted = observed.observation
    finally:
        capture.release()

    if emitted is None:
        raise ValueError("round-6 source did not emit a stable meld delta")
    candidate = meld_observation_candidate(emitted, source_sha256=actual_sha)
    reconstruction = reconstruct_public_candidates(
        [candidate], claim_window_seconds=1.0, assembly_delay_seconds=0.0,
    )
    upgrades = reconstruction["meld_upgrade_candidates"]
    pass_result = (
        emitted.details.get("previous_group_size") == 3
        and emitted.details.get("group_size") == 4
        and emitted.details.get("tile_identity_complete") is False
        and len(upgrades) == 1
        and upgrades[0]["previous_group_size"] == 3
        and upgrades[0]["current_group_size"] == 4
        and upgrades[0]["action_kind"] == "UNKNOWN"
        and not any(row["kind"] == "ADD_KONG" for row in reconstruction["actions"])
    )
    return {
        "schema_version": "issue69_round6_meld_upgrade_private_replay_v0_1",
        "development_only": True,
        "source_session": source_session,
        "source_sha256": actual_sha,
        "frame_size": list(FRAME_SIZE),
        "fps": fps,
        "target_selection": "reviewed_exact_source_bbox_coverage_only",
        "trace": trace,
        "emitted_observation": {
            "timestamp_seconds": emitted.timestamp_seconds,
            "frame": emitted.details.get("frame"),
            "kind": emitted.kind.value,
            "group_size": emitted.details.get("group_size"),
            "previous_group_size": emitted.details.get("previous_group_size"),
            "tile_identity_complete": emitted.details.get("tile_identity_complete"),
            "previous_meld": emitted.details.get("previous_meld"),
        },
        "replay_candidate": {
            "frame_index": candidate.frame_index,
            "meld_group_size": candidate.meld_group_size,
            "previous_meld_group_size": candidate.previous_meld_group_size,
            "tiles": list(candidate.tiles),
        },
        "meld_upgrade_candidates": upgrades,
        "result": "PASS" if pass_result else "FAIL",
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True)
    parser.add_argument("--source-session", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", required=True, help="PRIVATE output; never commit")
    args = parser.parse_args()
    report = replay_round6_meld_upgrade(
        args.video,
        source_session=args.source_session,
        expected_sha256=args.expected_sha256,
    )
    Path(args.output).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "result": report["result"],
        "emitted_observation": report["emitted_observation"],
        "meld_upgrade_candidate_count": len(report["meld_upgrade_candidates"]),
        "safe_for_runtime": report["safe_for_runtime"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
