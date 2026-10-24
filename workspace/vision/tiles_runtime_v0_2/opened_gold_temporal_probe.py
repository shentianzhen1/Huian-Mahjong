"""Sequential detector -> Gold SIFT shadow replay; never trusted Runtime advice."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time


def shadow_windows(observations, replay_rows):
    by_frame = {r['frame']: r for r in observations}
    rows = []
    for row in replay_rows:
        frames = row['frames']
        if len(frames) != 3 or len(set(frames)) != 3 or frames != sorted(frames):
            raise ValueError('Require three distinct ordered replay frames')
        samples = [by_frame[i] for i in row['frames']]
        if [s['full_frame_rgb_sha256'] for s in samples] != row['pixel_sha256']:
            raise ValueError('Replay/sample RGB mismatch')
        candidates = [s['candidate'] for s in samples]
        agreed = bool(all(c and c != 'UNKNOWN' for c in candidates)
                      and len(set(candidates)) == 1)
        rows.append(dict(frames=row['frames'], candidate_agreement=agreed,
            candidate=candidates[0] if agreed else None,
            whole_geometry_untrusted=row['geometry_untrusted'],
            baseline_advice_allowed=row['display_allowed']))
    return rows


def classify_frame(image, frame, session, classifier):
    from .dynamic_geometry import detect_dynamic_geometry
    from .runtime_reader import classification_crop_bbox
    geometry = detect_dynamic_geometry(image, frame=frame, session=session)
    gold = [c for c in geometry.components if c.region_candidate == 'gold']
    result = dict(frame=frame, full_frame_rgb_sha256=hashlib.sha256(image.tobytes()).hexdigest(),
        frame_geometry_untrusted=geometry.geometry_untrusted, candidate=None,
        status='gold_component_count_not_one')
    if len(gold) != 1:
        return result
    box = classification_crop_bbox(gold[0].pixel_bbox, frame_size=image.size,
        neighbors=[c.pixel_bbox for c in geometry.components if c.pixel_bbox != gold[0].pixel_bbox])
    x,y,w,h = box
    crop = image.crop((x,y,x+w,y+h))
    prediction = classifier.classify(crop)
    result.update(crop_bbox=list(box), crop_rgb_sha256=hashlib.sha256(crop.tobytes()).hexdigest(),
        candidate=prediction.tile_id if prediction.tile_id != 'UNKNOWN' else None,
        status='candidate' if prediction.tile_id != 'UNKNOWN' else 'no_unique_identity',
        method=prediction.method, evidence_count=prediction.evidence_count,
        second=prediction.second_best_evidence_count)
    # A visible Gold crop may be examined while whole-hand geometry is bad.
    # This shadow observation never changes that geometry or opens advice.
    return result


def probe_video(video_path, replay_path, dataset_root, *, lineage_path, exclude_matches):
    import cv2
    from PIL import Image
    from workspace.hint_alpha.replay_smoke import sha256
    from workspace.vision.concealed_template_match_lineage import (
        canonicalize_match_group, load_concealed_template_lineage,
    )
    from workspace.vision.tiles_v0_1.gold_classifier import GoldTileClassifier
    from workspace.vision.tiles_v0_1.labels import approved_labels
    replay = json.loads(Path(replay_path).read_text())
    if sha256(video_path) != replay['source_sha256']:
        raise ValueError('Video/replay source mismatch')
    lineage = load_concealed_template_lineage(lineage_path)
    excluded = {canonicalize_match_group(g) for g in exclude_matches}
    labels = approved_labels(dataset_root)
    training = [r for r in labels if r.get('sha256') not in lineage
                or lineage[r['sha256']].match_group not in excluded]
    classifier = GoldTileClassifier.from_labels(dataset_root, training)
    wanted = {i for r in replay['rows'] for i in r['frames']}
    observations = []
    cap = cv2.VideoCapture(str(video_path))
    started = time.perf_counter()
    fps = cap.get(cv2.CAP_PROP_FPS)
    try:
        if not cap.isOpened() or fps <= 0:
            raise ValueError('Cannot decode video with valid FPS')
        index = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if index in wanted:
                image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                observations.append(classify_frame(image, index, replay['session'], classifier))
            index += 1
    finally:
        cap.release()
    if {r['frame'] for r in observations} != wanted:
        raise ValueError('Video did not supply every replay frame')
    windows = shadow_windows(observations, replay['rows'])
    first = next((r['frames'][-1] for r in windows if r['candidate_agreement']), None)
    return dict(schema_version='opened_gold_temporal_shadow_v0_1',
        development_only=True, formal_promotion_evidence=False,
        runtime_changed=False, safe_for_runtime=False, safe_for_hint=False, safe_for_executor=False,
        candidate_counts_are_runtime_confidence=False, source_sha256=replay['source_sha256'],
        fps=fps, sampled_frames=len(observations),
        detected_gold_crops=sum('crop_bbox' in r for r in observations),
        frame_status_counts=dict(Counter(r['status'] for r in observations)),
        candidate_counts=dict(Counter(r['candidate'] or 'UNKNOWN' for r in observations)),
        windows=len(windows), candidate_agreement_windows=sum(r['candidate_agreement'] for r in windows),
        whole_geometry_trusted_agreement_windows=sum(r['candidate_agreement'] and not r['whole_geometry_untrusted'] for r in windows),
        first_candidate_agreement_source_seconds=first/fps if first is not None else None,
        excluded_known_matches=sorted(excluded),
        unresolved_lineage_training_labels=sum(r.get('sha256') not in lineage for r in training),
        elapsed_seconds=round(time.perf_counter()-started,3),
        observations=observations, window_results=windows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--replay', type=Path, required=True)
    parser.add_argument('--dataset', type=Path, default=Path('dataset/tiles_runtime_v0_2'))
    parser.add_argument('--lineage', type=Path, default=Path('references/vision/2026-10-01/concealed_template_match_lineage.development.json'))
    parser.add_argument('--exclude-match', action='append', default=[])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = probe_video(args.video, args.replay, args.dataset,
        lineage_path=args.lineage, exclude_matches=args.exclude_match)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('observations','window_results')}))


if __name__ == '__main__':
    main()
