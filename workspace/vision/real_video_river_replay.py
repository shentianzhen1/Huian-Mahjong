"""First source-qualified, read-only real-video river/action replay (#69).

The video is SHA-verified BEFORE decoding. This script never loads human truth
until the entire independent machine prediction trace has been assembled. It
never infers tile identity/turn, and it preserves the assembler's UNKNOWN grade.
All outputs are local; only sanitized summary counts belong in the public repo.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path
from typing import Any

from workspace.vision.real_video_public_probe import source_sha256
from workspace.vision.source_river_geometry import load_river_manifest, qualify_river_frame


SCHEMA_VERSION = "source_river_action_replay_v0_1"


def replay_rivers(video: str | Path, *, manifest_path: str | Path,
                  first_frame: int, last_frame: int,
                  truth_path: str | Path | None = None) -> dict[str, Any]:
    """Return machine-generated predictions and optional post-run development eval.

    No raw video, crop, private file URI, or screenshots are included in output.
    Source-identity errors and discontinuous timestamps abort, not silently rebase.
    """
    manifest = load_river_manifest(manifest_path)
    if type(first_frame) is not int or type(last_frame) is not int or first_frame < 0 or last_frame <= first_frame:
        raise ValueError("continuous frame range must have increasing nonnegative integers")
    if manifest.reviewed_frame_span is not None and (
        first_frame < manifest.reviewed_frame_span[0]
        or last_frame > manifest.reviewed_frame_span[1]
    ):
        raise ValueError("replay exceeds source-reviewed river interval")
    actual_hash = source_sha256(Path(video))
    if actual_hash != manifest.source_sha256:
        raise ValueError("video SHA256 mismatch; never import stale source annotations")
    # Vision is optional in core-only installs, so keep image-related imports
    # inside this function (like real_video_public_probe).
    import cv2
    from PIL import Image
    from workspace.vision.action_assembler import AssemblyConfig, TemporalActionAssembler
    from workspace.vision.action_attribution_eval import (
        PredictionBatch, evaluate_attribution, load_truth, prediction_from_action,
    )
    from workspace.vision.public_candidate_tracker import (
        CandidateChannel, PublicCandidateTracker, river_snapshot_from_channel,
    )
    from workspace.vision.public_observers import DiscardRiverObserver
    from workspace.vision.public_tile_detector import detect_public_tile_geometry

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError("video cannot be decoded")
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if count <= last_frame:
        cap.release()
        raise ValueError("requested frame range exceeds video")
    if (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))) != manifest.frame_size:
        cap.release()
        raise ValueError("source resolution does not match reviewed manifest")
    if not cap.set(cv2.CAP_PROP_POS_FRAMES, first_frame):
        cap.release()
        raise ValueError("failed to seek to requested first frame")

    tracker = PublicCandidateTracker(settle_frames=3, disappear_frames=2, maximum_gap_seconds=.5)
    observers = {z.actor: DiscardRiverObserver(settle_frames=3) for z in manifest.zones}
    channels = {z.actor: CandidateChannel(
        name="reviewed_" + z.actor + "_river", geometry_kinds=("single_face", "river_split_face"),
        zones=(z.bbox,), minimum_zone_coverage=.99,
    ) for z in manifest.zones}
    assembler = TemporalActionAssembler(AssemblyConfig(claim_window_seconds=.9, assembly_delay_seconds=.15))
    observations = []
    actions = []
    counts: Counter[str] = Counter()
    rejected_frames: dict[str,list[int]] = {a:[] for a in observers}
    previous_pts: float | None = None
    first_pts: float | None = None
    last_pts: float | None = None
    epochs: set[int] = set()
    try:
        for index in range(first_frame, last_frame + 1):
            success, image_bgr = cap.read()
            if not success:
                raise ValueError(f"missing source video frame {index}")
            pts = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
            if previous_pts is not None and pts <= previous_pts:
                raise ValueError(f"nonmonotonic source PTS at frame {index}")
            previous_pts = pts
            first_pts = pts if first_pts is None else first_pts
            last_pts = pts
            image = Image.fromarray(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))
            detected = detect_public_tile_geometry(image, frame=index, session=manifest.source_session)
            qualified = qualify_river_frame(image, detected, manifest=manifest, actual_sha256=actual_hash)
            tracked = tracker.observe(qualified.filtered_frame, timestamp_seconds=pts)
            epochs.add(tracked.stream_epoch)
            counts["detector_candidate_frame_instances"] += len(detected.candidates)
            counts["qualified_river_candidate_frame_instances"] += len(qualified.filtered_frame.candidates)
            counts["stable_track_frame_instances"] += len(tracked.stable_tracks)
            for event in tracked.events:
                counts["tracker_"+event.kind.value.lower()] += 1
            for actor in ("opponent", "player"):
                snapshot = river_snapshot_from_channel(tracked,channel=channels[actor],
                                                       actor=actor,timestamp_seconds=pts)
                if not qualified.actor_trust[actor]:
                    snapshot = replace(snapshot, trusted=False)
                    rejected_frames[actor].append(index)
                    counts[actor+"_untrusted_frames"] += 1
                observed = observers[actor].observe(snapshot)
                for issue in observed.issues:
                    counts[actor+"_"+issue] += 1
                if observed.observation is not None:
                    counts[actor+"_river_growth_observations"] += 1
                    observations.append(observed.observation)
                    actions.extend(assembler.ingest(observed.observation))
            actions.extend(assembler.advance_time(pts))
        actions.extend(assembler.flush())
    finally:
        cap.release()
    predictions = tuple(prediction_from_action(action) for action in actions)
    # No truth read or scoring occurred anywhere above this point.
    evaluation = None
    if truth_path is not None:
        truth = load_truth(truth_path)
        if truth.source_session != manifest.source_session:
            raise ValueError("truth session does not match video source")
        evaluation = evaluate_attribution(truth, PredictionBatch(actual_hash, predictions))
    counts["assembled_actions"] = len(actions)
    counts["unknown_graded_actions"] = sum(a.evidence_grade.value == "UNKNOWN" for a in actions)
    counts["known_tile_actions"] = sum(a.tile is not None for a in actions)
    return {
        "schema_version": SCHEMA_VERSION,
        "source_session": manifest.source_session,
        "source_sha256": actual_hash,
        "frames_decoded": last_frame-first_frame+1,
        "frame_range": [first_frame,last_frame],
        "time_seconds": [round(first_pts,6),round(last_pts,6)],
        "stream_epochs": sorted(epochs),
        "counts": dict(counts),
        "untrusted_frame_indexes_by_actor": rejected_frames,
        "machine_predictions": {
            "schema_version": "public_action_attribution_eval_v0_1",
            "source_sha256": actual_hash,
            "actions": [{
                "timestamp_seconds": p.timestamp_seconds,
                "source_session": p.source_session,
                "stream_epoch": p.stream_epoch,
                "kind": p.kind,
                "actor": p.actor,
                "evidence_grade": p.evidence_grade,
                "evidence_refs": list(p.evidence_refs),
                "confidence": p.confidence,
                "tile": p.tile,
                "turn_actor": p.turn_actor,
            } for p in predictions],
        },
        "development_evaluation": evaluation,
        "tile_identity_policy": "UNKNOWN until independent public tile identity evidence",
        "turn_actor_policy": "UNKNOWN until independent turn evidence",
        "source_disjoint_holdout": False,
        "formal_promotion_evidence": False,
        "safe_for_executor": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--first-frame",type=int,required=True)
    parser.add_argument("--last-frame",type=int,required=True)
    parser.add_argument("--truth",help="Optional frozen development truth; loaded only after prediction assembly")
    parser.add_argument("--output",required=True,help="PRIVATE local full trace; never commit video identifiers/crops")
    args=parser.parse_args()
    result=replay_rivers(args.video,manifest_path=args.manifest,first_frame=args.first_frame,
                         last_frame=args.last_frame,truth_path=args.truth)
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({key:result[key] for key in ("frames_decoded","stream_epochs","counts",
          "development_evaluation","safe_for_executor")},ensure_ascii=False))

if __name__=="__main__":
    main()
