"""Development-only input A/B; never updates Runtime confidence or identity."""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
from PIL import Image

from workspace.vision.tiles_v0_1.labels import approved_labels
from workspace.vision.tiles_v0_1.template_classifier import _feature
from .runtime_reader import CLASSIFIER_REGIONS, _canonical_region, _training_labels, read_stable_frames


def probe(video, dataset, *, source_session=None):
    source_hash = hashlib.sha256()
    with Path(video).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            source_hash.update(chunk)
    digest = source_hash.hexdigest()
    session = source_session or 'local-video-' + digest[:16]
    # Keep this Vision-only development probe independent of the Alpha UI layer.
    cap = cv2.VideoCapture(str(video))
    samples = []
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        if not cap.isOpened() or fps <= 0:
            raise ValueError('Invalid video')
        stride = max(1, int(round(0.3 * fps)))
        for index in range(2 * stride + 1):
            if not cap.grab():
                break
            if index % stride == 0:
                ok, pixels = cap.retrieve()
                if not ok:
                    break
                samples.append((index, index / fps, Image.fromarray(cv2.cvtColor(pixels, cv2.COLOR_BGR2RGB))))
    finally:
        cap.release()
    if len(samples) < 3:
        raise ValueError('Require three original sampled frames')
    report = read_stable_frames([x[2] for x in samples], dataset,
                               frame_ids=[x[0] for x in samples], session=session)
    image = samples[-1][2]
    bank = []
    for label in _training_labels(approved_labels(dataset), session):
        with Image.open(Path(dataset) / label['image']) as reference:
            region = _canonical_region(label['region'])
            bank.append((label['tile_id'], region, _feature(reference, region=region),
                         _feature(reference, region='gold_region')))
    rows = []
    for component in report.get('components', []):
        if component['tile_id'] != 'UNKNOWN' or component['region_candidate'] not in CLASSIFIER_REGIONS:
            continue
        region = CLASSIFIER_REGIONS[component['region_candidate']]
        results = {}
        for variant in ('current_region', 'tight_region', 'symmetric_pooled_gold'):
            bbox = component['pixel_bbox'] if variant != 'current_region' else component.get('classification_crop_bbox', component['pixel_bbox'])
            x, y, w, h = bbox
            pooled = variant == 'symmetric_pooled_gold'
            sample = _feature(image.crop((x, y, x + w, y + h)), region='gold_region' if pooled else region)
            scores = {}
            for tile, ref_region, current, gold in bank:
                if not pooled and ref_region != region:
                    continue
                score = float(cv2.matchTemplate(sample, gold if pooled else current, cv2.TM_CCOEFF_NORMED)[0, 0])
                scores[tile] = max(scores.get(tile, -1.0), score)
            ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:3]
            results[variant] = {'bbox': list(bbox), 'ranking': [{'tile': tile, 'raw_ncc': round(score, 6)} for tile, score in ranked]}
        rows.append({'region': component['region_candidate'], 'gold_skin': component.get('gold_skin', False),
                     'runtime_reason': component['identity_reason'], 'variants': results})
    return {'schema_version': 'identity_input_probe_v0_1', 'source_sha256': digest,
            'frame_ids': [x[0] for x in samples], 'source_seconds': [x[1] for x in samples],
            'pixel_sha256': [hashlib.sha256(x[2].tobytes()).hexdigest() for x in samples],
            'original_session_binding': 'explicit_unverified_by_probe' if source_session else 'sha_derived_no_original_match_exclusion_claim',
            'domain_coverage': report['classification_domain_coverage'], 'rows': rows,
            'formal_promotion_evidence': False, 'runtime_changed': False,
            'note': 'Raw A/B correlations are not Runtime confidence, identity acceptance or independent accuracy.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video', type=Path)
    parser.add_argument('--dataset', type=Path, default=Path('dataset/tiles_runtime_v0_2'))
    parser.add_argument('--source-session')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = probe(args.video, args.dataset, source_session=args.source_session)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
