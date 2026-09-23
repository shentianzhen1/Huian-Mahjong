"""Source-hashed real-video geometry/tracker probe; NOT an action classifier.

Runs the existing public detector and candidate tracker on *every decoded frame*
of a bounded interval. The reviewed development profiles are diagnostics only:
APPEARED, a stable track, or a selected profile never implies DISCARD/actor.
The original video stays local; the JSON output stores only anonymous bboxes.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from workspace.vision.public_candidate_tracker import PublicCandidateTracker, TrackEventKind
from workspace.vision.public_channel_profiles import load_channel_manifest

SCHEMA_VERSION = 'real_public_geometry_probe_v0_1'
_SHA256 = re.compile(r'^[0-9a-f]{64}$')


def source_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def probe_video(
    video: str | Path, *, source_session: str, expected_sha256: str,
    first_frame: int, last_frame: int, profile_manifest: str | Path,
) -> dict[str, Any]:
    """Read the immutable source once; never read truth to produce candidates.

    Epoch=0 is valid only for uninterrupted frame-by-frame decoding. A missing
    frame, time reversal, or different video hash aborts instead of bridging it.
    """
    if not isinstance(source_session, str) or not source_session.strip():
        raise ValueError('source_session is required')
    if not isinstance(expected_sha256, str) or not _SHA256.fullmatch(expected_sha256):
        raise ValueError('expected_sha256 must be lowercase 64-character SHA256')
    if type(first_frame) is not int or type(last_frame) is not int or first_frame < 0 or last_frame <= first_frame:
        raise ValueError('frame range must be increasing nonnegative integers')
    path = Path(video)
    actual_sha256 = source_sha256(path)
    if actual_sha256 != expected_sha256:
        raise ValueError('video SHA256 mismatch; no cross-source replay allowed')
    profiles = load_channel_manifest(profile_manifest)
    if not profiles.excluded_from_formal_promotion:
        raise ValueError('profiles must be development-only')
    # Keep optional Vision dependencies out of core-only imports.
    import cv2
    from PIL import Image
    from workspace.vision.public_tile_detector import detect_public_tile_geometry

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError('video cannot be decoded')
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if count <= last_frame:
        capture.release()
        raise ValueError('requested frame range exceeds recording')
    capture.set(cv2.CAP_PROP_POS_FRAMES, first_frame)
    tracker = PublicCandidateTracker(settle_frames=3, disappear_frames=2, maximum_gap_seconds=0.5)
    selected = [(p.name, p.to_candidate_channel()) for p in profiles.profiles]
    appearances: list[dict[str, Any]] = []
    observed_counts: Counter[str] = Counter()
    profile_appearances: Counter[str] = Counter()
    profile_stable_frames: Counter[str] = Counter()
    epochs: set[int] = set()
    previous_time: float | None = None
    first_time: float | None = None
    last_time: float | None = None
    try:
        for frame_idx in range(first_frame, last_frame + 1):
            success, image_bgr = capture.read()
            if not success:
                raise ValueError(f'missing source frame {frame_idx}')
            timestamp = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000
            if previous_time is not None and timestamp <= previous_time:
                raise ValueError(f'nonmonotonic video PTS at frame {frame_idx}')
            previous_time = timestamp
            first_time = timestamp if first_time is None else first_time
            last_time = timestamp
            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            detection = detect_public_tile_geometry(
                Image.fromarray(image_rgb), frame=frame_idx, session=source_session,
            )
            tracked = tracker.observe(detection, timestamp_seconds=timestamp)
            epochs.add(tracked.stream_epoch)
            observed_counts['detector_candidates'] += len(detection.candidates)
            observed_counts['peak_candidates_per_frame'] = max(
                observed_counts['peak_candidates_per_frame'], len(detection.candidates),
            )
            observed_counts['stable_track_frame_instances'] += len(tracked.stable_tracks)
            for name, channel in selected:
                if any(channel.accepts(track) for track in tracked.stable_tracks):
                    profile_stable_frames[name] += 1
            for event in tracked.events:
                observed_counts[event.kind.value] += 1
                matches = [name for name, channel in selected if channel.accepts(event.track)]
                if event.kind is TrackEventKind.APPEARED:
                    profile_appearances.update(matches)
                appearances.append({
                    'frame': frame_idx,
                    'timestamp_seconds': round(timestamp, 6),
                    'event': event.kind.value,
                    'track_id': event.track.track_id,
                    'geometry_kind': event.track.geometry_kind,
                    'normalized_bbox': list(event.track.normalized_bbox),
                    'profile_matches': matches,
                })
    finally:
        capture.release()
    return {
        'schema_version': SCHEMA_VERSION,
        'source_session': source_session,
        'source_sha256': actual_sha256,
        'frame_range': [first_frame, last_frame],
        'first_pts_seconds': round(first_time, 6),
        'last_pts_seconds': round(last_time, 6),
        'frames_decoded': last_frame - first_frame + 1,
        'stream_epochs': sorted(epochs),
        'detector': 'workspace.vision.public_tile_detector.detect_public_tile_geometry',
        'tracker': 'workspace.vision.public_candidate_tracker.PublicCandidateTracker',
        'development_profile_names': [p.name for p in profiles.profiles],
        'counts': dict(observed_counts),
        'profile_appearances': dict(profile_appearances),
        'profile_stable_frames': dict(profile_stable_frames),
        'track_events': appearances,
        'reconstructed_actions': [],
        'action_metric': None,
        'reason_no_actions': 'reviewed profiles do not establish source-qualified river ownership or DISCARD semantics',
        'source_disjoint_holdout': False,
        'formal_promotion_evidence': False,
        'safe_for_executor': False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', required=True)
    parser.add_argument('--source-session', required=True)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--first-frame', required=True, type=int)
    parser.add_argument('--last-frame', required=True, type=int)
    parser.add_argument('--profile-manifest', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = probe_video(
        args.video,
        source_session=args.source_session,
        expected_sha256=args.source_sha256,
        first_frame=args.first_frame,
        last_frame=args.last_frame,
        profile_manifest=args.profile_manifest,
    )
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in (
        'frames_decoded', 'stream_epochs', 'counts', 'profile_appearances',
        'profile_stable_frames', 'reason_no_actions', 'safe_for_executor',
    )}, ensure_ascii=False))


if __name__ == '__main__':
    main()
