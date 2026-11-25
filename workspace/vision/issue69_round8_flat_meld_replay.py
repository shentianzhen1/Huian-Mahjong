"""Private exact-source regression for two reviewed round-8 FLAT meld onsets.

This runner verifies only structural public-meld facts from frozen stable
windows. It intentionally skips the action animation interval and never turns
human PENG/CHI knowledge into machine action truth.

Pipeline:
public detector -> full-frame meld structure bridge -> MeldSnapshotObserver ->
MELD_DELTA. Private source SHA/frame details stay in the local output only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from workspace.vision.public_meld_structure_frame_bridge import (
    review_public_meld_structure_frame,
)
from workspace.vision.public_observers import MeldSnapshotObserver
from workspace.vision.public_tile_detector import detect_public_tile_geometry

_SHA = re.compile(r"^[a-f0-9]{64}$")
FRAME_SIZE = (1108, 512)

PLAYER_BASELINE = (3425, 3426, 3427, 3428, 3429)
PLAYER_STABLE = (3459, 3460, 3461, 3462, 3463)
OPPONENT_BASELINE = (3505, 3506, 3507, 3508, 3509)
OPPONENT_STABLE = (3532, 3533, 3534, 3535, 3536)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def replay_round8_flat_melds(
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
    if (
        int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
        int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    ) != FRAME_SIZE:
        capture.release()
        raise ValueError("source resolution does not match reviewed round-8 source")

    traces = []
    observers = {
        "player": MeldSnapshotObserver(settle_frames=5),
        "opponent": MeldSnapshotObserver(settle_frames=5),
    }
    emitted = {"player": [], "opponent": []}

    def consume(actor: str, frame_index: int, *, baseline: bool) -> None:
        geometry_kind = "bottom_group" if actor == "player" else "top_group"
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
        groups = tuple(
            candidate for candidate in detection.candidates
            if candidate.geometry_kind == geometry_kind
        )
        review = review_public_meld_structure_frame(
            image,
            groups,
            timestamp_seconds=pts,
            actor=actor,
            source_session=source_session,
            stream_epoch=0,
            frame_index=frame_index,
            source_frame_verified=True,
            public_meld_region_verified=True,
            empty_meld_set_verified=(baseline and actor == "player" and not groups),
            evidence_refs=(f"round8-reviewed-{actor}-meld:frame:{frame_index}",),
        )
        if not review.snapshot.trusted:
            raise ValueError(
                f"reviewed stable frame became untrusted at {frame_index}: {review.issues}"
            )
        observed = observers[actor].observe(review.snapshot)
        traces.append({
            "actor": actor,
            "frame_index": frame_index,
            "timestamp_seconds": round(pts, 6),
            "baseline_window": baseline,
            "group_count": len(review.snapshot.groups),
            "structural_face_counts": [len(group.tiles) for group in review.snapshot.groups],
            "stack_states": [item.geometry.stack_state for item in review.group_reviews],
            "observer_stable": observed.stable,
            "observer_trusted": observed.trusted,
            "observer_issues": list(observed.issues),
        })
        if observed.observation is not None:
            emitted[actor].append(observed.observation)

    try:
        for frame in PLAYER_BASELINE:
            consume("player", frame, baseline=True)
        for frame in PLAYER_STABLE:
            consume("player", frame, baseline=False)
        for frame in OPPONENT_BASELINE:
            consume("opponent", frame, baseline=True)
        for frame in OPPONENT_STABLE:
            consume("opponent", frame, baseline=False)
    finally:
        capture.release()

    machine_events = []
    for actor in ("player", "opponent"):
        for observation in emitted[actor]:
            machine_events.append({
                "actor": actor,
                "timestamp_seconds": observation.timestamp_seconds,
                "frame": observation.details.get("frame"),
                "kind": observation.kind.value,
                "group_size": observation.details.get("group_size"),
                "previous_group_size": observation.details.get("previous_group_size"),
                "tile_identity_complete": observation.details.get("tile_identity_complete"),
            })

    pass_result = (
        len(emitted["player"]) == 1
        and len(emitted["opponent"]) == 1
        and emitted["player"][0].details.get("frame") == PLAYER_STABLE[-1]
        and emitted["opponent"][0].details.get("frame") == OPPONENT_STABLE[-1]
        and emitted["player"][0].details.get("group_size") == 3
        and emitted["opponent"][0].details.get("group_size") == 3
        and emitted["player"][0].details.get("tile_identity_complete") is False
        and emitted["opponent"][0].details.get("tile_identity_complete") is False
        and "previous_group_size" not in emitted["player"][0].details
        and "previous_group_size" not in emitted["opponent"][0].details
    )
    return {
        "schema_version": "issue69_round8_flat_meld_private_replay_v0_1",
        "development_only": True,
        "source_session": source_session,
        "source_sha256": actual_sha,
        "frame_size": list(FRAME_SIZE),
        "review_policy": "frozen_stable_windows_only_animation_not_machine_truth",
        "trace": traces,
        "machine_events": machine_events,
        "result": "PASS" if pass_result else "FAIL",
        "human_action_semantics_used_for_machine_result": False,
        "tile_identity_policy": "UNKNOWN",
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
    report = replay_round8_flat_melds(
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
        "machine_events": report["machine_events"],
        "safe_for_runtime": report["safe_for_runtime"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
