"""Private, source-hashed, unlabeled public-river review-crop export (#69).

No manual truth, tile classifier, or action prediction is loaded. This is a
review queue of stable geometry candidates, NOT a source of approved labels.
Never write private pixel crops inside the public repository.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from workspace.vision.real_video_public_probe import source_sha256
from workspace.vision.source_river_geometry import load_river_manifest, qualify_river_frame

SCHEMA_VERSION = "source_river_review_queue_v0_1"


def export_review_queue(
    video: str | Path, *, manifest_path: str | Path,
    first_frame: int, last_frame: int, output_dir: str | Path,
) -> dict[str, Any]:
    """Export only stable, source-qualified river crops for later human review.

    Uses the detector/tracker independently of frozen action truth. Rejects
    source mismatch, bad span, output inside repo, or existing output files.
    """
    if (type(first_frame) is not int or type(last_frame) is not int
            or first_frame < 0 or last_frame < first_frame):
        raise ValueError("review frame interval must be increasing integers")
    manifest = load_river_manifest(manifest_path)
    if manifest.reviewed_frame_span is not None and (
        first_frame < manifest.reviewed_frame_span[0]
        or last_frame > manifest.reviewed_frame_span[1]
    ):
        raise ValueError("review queue exceeds source-reviewed river interval")
    actual_hash = source_sha256(Path(video))
    if actual_hash != manifest.source_sha256:
        raise ValueError("video SHA256 mismatch; cannot export review crops")
    destination = Path(output_dir).resolve()
    repository = Path(__file__).resolve().parents[2]
    if destination == repository or repository in destination.parents:
        raise ValueError("private pixel review output must be outside repository")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("review output directory must be empty")

    # Vision imports remain optional for non-Vision installations.
    import cv2
    from PIL import Image
    from workspace.vision.public_candidate_tracker import (
        CandidateChannel, PublicCandidateTracker, TrackEventKind,
    )
    from workspace.vision.public_tile_detector import detect_public_tile_geometry

    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise ValueError("video cannot be decoded")
    if (int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) <= last_frame
            or (int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
                int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))) != manifest.frame_size):
        capture.release()
        raise ValueError("source frame count/resolution does not match manifest")
    if not capture.set(cv2.CAP_PROP_POS_FRAMES, first_frame):
        capture.release()
        raise ValueError("could not seek to review interval")

    channels = {zone.actor: CandidateChannel(
        name="review_" + zone.actor,
        geometry_kinds=("single_face", "river_split_face"),
        zones=(zone.bbox,), minimum_zone_coverage=.99,
    ) for zone in manifest.zones}
    tracker = PublicCandidateTracker(settle_frames=3, disappear_frames=2,
                                     maximum_gap_seconds=.5)
    entries: list[dict[str, Any]] = []
    seen_tracks: set[int] = set()
    previous_pts: float | None = None
    try:
        for index in range(first_frame, last_frame + 1):
            okay, image_bgr = capture.read()
            if not okay:
                raise ValueError(f"missing video source frame {index}")
            pts = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000
            if previous_pts is not None and pts <= previous_pts:
                raise ValueError(f"nonmonotonic PTS at frame {index}")
            previous_pts = pts
            frame_image = Image.fromarray(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))
            detection = detect_public_tile_geometry(
                frame_image, frame=index, session=manifest.source_session,
            )
            qualified = qualify_river_frame(
                frame_image, detection, manifest=manifest, actual_sha256=actual_hash,
            )
            tracked = tracker.observe(qualified.filtered_frame, timestamp_seconds=pts)
            for event in tracked.events:
                if (event.kind is not TrackEventKind.APPEARED
                        or event.track.track_id in seen_tracks):
                    continue
                matches = [actor for actor, channel in channels.items()
                           if (qualified.actor_trust[actor]
                               and channel.accepts(event.track))]
                if len(matches) != 1:
                    continue
                track = event.track
                x, y, width, height = track.normalized_bbox
                left = round(x * manifest.frame_size[0])
                top = round(y * manifest.frame_size[1])
                right = round((x + width) * manifest.frame_size[0])
                bottom = round((y + height) * manifest.frame_size[1])
                if right <= left or bottom <= top:
                    continue
                crop = frame_image.crop((left, top, right, bottom))
                name = f"{matches[0]}_f{index:06d}_track{track.track_id:04d}.png"
                destination.mkdir(parents=True, exist_ok=True)
                path = destination / name
                crop.save(path)
                entries.append({
                    "review_id": name.removesuffix(".png"),
                    "frame": index,
                    "timestamp_seconds": round(pts, 6),
                    "stream_epoch": tracked.stream_epoch,
                    "track_id": track.track_id,
                    "screen_side_actor": matches[0],
                    "normalized_bbox": list(track.normalized_bbox),
                    "geometry_kind": track.geometry_kind,
                    "crop_file": name,
                    "crop_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "tile_id": None,
                    "turn_actor": None,
                    "action_kind": None,
                    "review_status": "pending",
                })
                seen_tracks.add(track.track_id)
    finally:
        capture.release()

    # Geometry-only duplicate hints: a split may re-introduce the old tile as
    # a new tracker ID. Retain both crops for review, never auto-promote a label.
    for row in entries:
        x, y, w, h = row["normalized_bbox"]
        possible = []
        for prior in entries:
            if (prior["frame"] >= row["frame"]
                    or prior["screen_side_actor"] != row["screen_side_actor"]
                    or row["timestamp_seconds"] - prior["timestamp_seconds"] > 15):
                continue
            px, py, pw, ph = prior["normalized_bbox"]
            overlap = (max(0.0, min(x + w, px + pw) - max(x, px))
                       * max(0.0, min(y + h, py + ph) - max(y, py)))
            if overlap / min(w * h, pw * ph) >= 0.75:
                possible.append(prior["review_id"])
        row["possible_repeat_of"] = possible
    result = {
        "schema_version": SCHEMA_VERSION,
        "source_session": manifest.source_session,
        "source_sha256": actual_hash,
        "frame_range": [first_frame, last_frame],
        "review_kind": "private_unlabeled_development_geometry",
        "formal_promotion_evidence": False,
        "safe_for_executor": False,
        "label_reuse_forbidden": True,
        "candidates": entries,
    }
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "review_queue.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--first-frame", type=int, required=True)
    parser.add_argument("--last-frame", type=int, required=True)
    parser.add_argument("--output-dir", required=True,
                        help="Private local directory OUTSIDE the public repository")
    args = parser.parse_args()
    result = export_review_queue(
        args.video, manifest_path=args.manifest, first_frame=args.first_frame,
        last_frame=args.last_frame, output_dir=args.output_dir,
    )
    print(json.dumps({"candidates": len(result["candidates"]),
                      "review_kind": result["review_kind"],
                      "safe_for_executor": result["safe_for_executor"]}))


if __name__ == "__main__":
    main()
