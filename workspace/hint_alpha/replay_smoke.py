"""Private, source-locked frame/video replay through the live advisory boundary.

Outputs are development diagnostics, never formal promotion evidence.
"""
from __future__ import annotations

import argparse
from collections import deque
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import time

from .runtime_pipeline import evaluate_runtime_report


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def evaluate_burst(samples, *, session, dataset_root, epoch=0, reader=None):
    """Samples are unique (frame index, source seconds, RGB image) captures."""
    ids = [item[0] for item in samples]
    times = [item[1] for item in samples]
    if len(samples) != 3 or len(set(ids)) != 3 or ids != sorted(ids):
        raise ValueError('Require three distinct ordered source frame indices')
    if any(not math.isfinite(t) or t < 0 for t in times):
        raise ValueError("Source timestamps must be finite and nonnegative")
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError('Source frame timestamps must increase')
    if reader is None:
        from workspace.vision.tiles_runtime_v0_2.runtime_reader import read_stable_frames
        reader = read_stable_frames
    started = time.perf_counter()
    report = reader([item[2] for item in samples], dataset_root,
                    frame_ids=ids, session=session, confidence_threshold=0.82)
    report['stream_epoch'] = epoch
    # Sparse screenshots may diagnose pixels, but do not establish live stability.
    if times[-1] - times[0] > 0.8:
        report = {**report, 'geometry_untrusted': True,
                  'geometry_issues': ['sparse_source_burst']}
    advisory = evaluate_runtime_report(report, captured=times[-1], experimental=True)
    return {
        'frames': ids, 'source_seconds': times,
        'pixel_sha256': [hashlib.sha256(item[2].tobytes()).hexdigest() for item in samples],
        'elapsed_ms': round((time.perf_counter() - started) * 1000, 3),
        'snapshot': asdict(advisory.snapshot), 'hint': asdict(advisory.hint),
        'display_allowed': advisory.display_allowed,
        'sparse_source_burst': times[-1] - times[0] > 0.8,
        'geometry_issues': report.get('geometry_issues', []),
        'safe_for_executor': False,
    }


def manifest_samples(path):
    from PIL import Image
    path = Path(path)
    source = json.loads(path.read_text(encoding='utf-8'))
    if not source.get('source_sha256') or not source.get('evidence_id'):
        raise ValueError('Frame manifest requires source SHA and evidence_id')
    for entry in source['selected_frames']:
        image_path = path.parent / entry['file']
        if sha256(image_path) != entry['sha256']:
            raise ValueError('Frame file SHA mismatch')
        with Image.open(image_path) as image:
            yield (entry['frame_index'], entry['time_ms'] / 1000, image.convert('RGB'))


def video_samples(path, *, expected_sha, start, duration, stride):
    import cv2
    from PIL import Image
    if sha256(path) != expected_sha:
        raise ValueError('Video source SHA mismatch')
    cap = cv2.VideoCapture(str(path))
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not cap.isOpened() or fps <= 0:
            raise ValueError('Video cannot be decoded with valid FPS')
        first, last = int(start * fps), int((start + duration) * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, first)
        for index in range(first, last):
            ok, frame = cap.read()
            if not ok:
                break
            if (index - first) % stride == 0:
                pts = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
                yield (index, pts, Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
    finally:
        cap.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--video', type=Path)
    group.add_argument('--frame-manifest', type=Path)
    parser.add_argument('--source-sha256')
    parser.add_argument('--start', type=float, default=0)
    parser.add_argument('--duration', type=float, default=3)
    parser.add_argument('--stride', type=int, default=3)
    parser.add_argument('--dataset', type=Path, default=Path('dataset/tiles_runtime_v0_2'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--require-accepted', action='store_true',
                        help='Fail acceptance if no trusted structural advice window exists')
    args = parser.parse_args()
    if args.stride < 1 or args.start < 0 or args.duration <= 0:
        parser.error('Require positive duration/stride and nonnegative start')
    if args.video:
        if not args.source_sha256:
            parser.error('--video requires --source-sha256')
        digest = args.source_sha256
        session = 'private-replay-' + digest[:16]
        samples = video_samples(args.video, expected_sha=digest, start=args.start,
                                duration=args.duration, stride=args.stride)
    else:
        manifest = json.loads(args.frame_manifest.read_text(encoding='utf-8'))
        digest, session = manifest['source_sha256'], manifest['evidence_id']
        samples = manifest_samples(args.frame_manifest)
    window = deque(maxlen=3)
    rows = []
    for sample in samples:
        window.append(sample)
        if len(window) == 3:
            rows.append(evaluate_burst(tuple(window), session=session, dataset_root=args.dataset))
    if not rows:
        raise ValueError('Source contains fewer than three decoded samples')
    result = {
        'schema_version': 'hint_alpha_replay_smoke_v0_1',
        'source_sha256': digest, 'session': session,
        'original_match_count': 1, 'formal_promotion_evidence': False,
        'safe_for_executor': False, 'identity_threshold': 0.82,
        'clock': 'offline_source_time_not_live_latency_gate',
        'windows_capture_validated': False,
        'accepted_windows': sum(row['display_allowed'] for row in rows),
        'blocked_windows': sum(not row['display_allowed'] for row in rows),
        'rows': rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}))
    if args.require_accepted and not result['accepted_windows']:
        raise SystemExit('Acceptance incomplete: zero trusted advice windows; report retained')


if __name__ == '__main__':
    main()
