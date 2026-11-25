"""Private, reviewed whole-hand A/B for client artwork; never Runtime intake."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

from .development_asset_intake import build_intake, STANDARD_TILES
from .concealed_template_match_lineage import (
    canonicalize_match_group, load_concealed_template_lineage,
    qualify_concealed_template_labels, verify_lineage_evidence_paths,
)
from .tiles_runtime_v0_2.whole_hand_tight_fallback_probe import _load_baseline


THRESHOLD = 0.82


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def private_crop_path(export, sample_id, crop_ref):
    """A report cannot read another file by escaping its private crop tree."""
    if not all(isinstance(value, str) and value for value in (sample_id, crop_ref)):
        raise ValueError('sample ID and private crop reference are required')
    if re.fullmatch(r'[A-Za-z0-9_.-]+', sample_id) is None or sample_id in {'.', '..'}:
        raise ValueError('sample ID must be an opaque directory name')
    root = (Path(export).resolve().parent / 'crops').resolve()
    sample_root = (root / sample_id).resolve()
    path = (sample_root / crop_ref).resolve()
    if not sample_root.is_relative_to(root) or not path.is_relative_to(sample_root):
        raise ValueError('private crop reference escapes crop directory')
    if not path.is_file():
        raise ValueError('reviewed query crop is unavailable')
    return path


def reviewed_samples(baseline, lock, export_sha):
    if not isinstance(lock, dict):
        raise ValueError('review lock must be an object')
    threshold = baseline.get('confidence_threshold')
    if type(threshold) not in (int, float) or not math.isfinite(threshold) or threshold != THRESHOLD:
        raise ValueError('baseline export must retain the frozen 0.82 threshold')
    if (lock.get('schema_version') != 'client_artwork_ab_review_lock_v0_1'
            or lock.get('development_only') is not True
            or lock.get('reviewed') is not True
            or not isinstance(lock.get('reviewer'), str) or not lock['reviewer'].strip()
            or lock.get('baseline_export_sha256') != export_sha
            or lock.get('source_sha256') != baseline['source']['sha256']
            or lock.get('original_match_group') != baseline['original_match_group']):
        raise ValueError('review lock must bind explicitly reviewed development truth to this export/source')
    selected = lock.get('samples')
    if not isinstance(selected, list) or not selected:
        raise ValueError('review lock must select complete whole-hand samples')
    index = {}
    for sample in baseline['samples']:
        identifier = sample.get('sample_id')
        if not isinstance(identifier, str) or identifier in index:
            raise ValueError('ambiguous baseline sample ID')
        index[identifier] = sample
    result, seen = [], set()
    for row in selected:
        identifier = row.get('sample_id')
        if not isinstance(identifier, str) or identifier in seen or identifier not in index:
            raise ValueError('duplicate or unknown reviewed sample')
        seen.add(identifier)
        sample = index[identifier]
        truth = row.get('truth_tiles')
        slots = sample.get('alignment', {}).get('slots')
        if (sample.get('truth', {}).get('gold_skinned_draw') is not False
                or not isinstance(truth, list) or not truth
                or any(tile not in STANDARD_TILES for tile in truth)
                or not isinstance(slots, list) or not slots
                or [slot.get('truth_tile') for slot in slots] != truth):
            raise ValueError('complete reviewed ordinary slot truth is required; Gold is out of scope')
        concealed = sample.get('truth', {}).get('concealed_hand')
        draw = sample.get('truth', {}).get('draw_visual')
        if (not isinstance(concealed, list) or (draw is not None and draw not in STANDARD_TILES)
                or Counter(concealed + ([] if draw is None else [draw])) != Counter(truth)):
            raise ValueError('slot truth does not cover the complete reviewed hand/draw')
        regions = Counter(slot.get('region') for slot in slots)
        keys = [(slot.get('region'), slot.get('slot')) for slot in slots]
        refs = [slot.get('private_crop_ref') for slot in slots]
        if (regions.get('hand', 0) != len(concealed)
                or regions.get('draw_visual', 0) != (0 if draw is None else 1)
                or set(regions) - {'hand', 'draw_visual'}
                or len(set(keys)) != len(keys) or len(set(refs)) != len(refs)
                or any(type(slot.get('slot')) is not int or slot['slot'] < 0 for slot in slots)
                or any(not isinstance(ref, str) or not ref for ref in refs)):
            raise ValueError('complete unique hand/draw crop slots are required')
        if sample.get('alignment', {}).get('status') == 'manual_alignment_required':
            raise ValueError('unresolved crop alignment cannot establish exact whole hands')
        result.append(sample)
    return result


def gated_prediction(prediction, covered, support):
    from .tiles_runtime_v0_2.runtime_reader import identity_gate, CONCEALED_IDENTITY_GATE_REGION
    if prediction is None:
        return {'candidate': None, 'confidence': None, 'accepted': 'UNKNOWN', 'reason': 'no_real_training_templates'}
    score = float(prediction.confidence)
    if prediction.tile_id not in STANDARD_TILES or not math.isfinite(score) or not 0 <= score <= 1:
        return {'candidate': None, 'confidence': None, 'accepted': 'UNKNOWN', 'reason': 'invalid_prediction'}
    tile, reason = identity_gate(prediction.tile_id, score, region=CONCEALED_IDENTITY_GATE_REGION,
        covered_classes=covered, cross_session_classes={CONCEALED_IDENTITY_GATE_REGION: support},
        confidence_threshold=THRESHOLD)
    return {'candidate': prediction.tile_id, 'confidence': score, 'accepted': tile, 'reason': reason}


def primary_first_prediction(baseline, candidate):
    return dict(baseline if baseline['accepted'] != 'UNKNOWN' else candidate)


def summarize(samples, variant):
    tiles = [slot for sample in samples for slot in sample['slots']]
    raw = sum(slot[variant]['candidate'] == slot['truth_tile'] for slot in tiles)
    accepted = [slot for slot in tiles if slot[variant]['accepted'] != 'UNKNOWN']
    correct = sum(slot[variant]['accepted'] == slot['truth_tile'] for slot in accepted)
    return {'truth_tiles': len(tiles), 'raw_correct': raw, 'accepted': len(accepted),
            'accepted_correct': correct, 'wrong_accepted': len(accepted) - correct,
            'rejected': len(tiles) - len(accepted), 'whole_hands': len(samples),
            'exact_raw_hands': sum(all(s[variant]['candidate'] == s['truth_tile'] for s in sample['slots']) for sample in samples),
            'exact_accepted_hands': sum(all(s[variant]['accepted'] == s['truth_tile'] for s in sample['slots']) for sample in samples),
            'fully_accepted_wrong_hands': sum(all(s[variant]['accepted'] != 'UNKNOWN' for s in sample['slots'])
                and any(s[variant]['accepted'] != s['truth_tile'] for s in sample['slots']) for sample in samples),
            'rejection_reasons': dict(Counter(slot[variant]['reason'] for slot in tiles if slot[variant]['accepted'] == 'UNKNOWN'))}


def evaluate(dataset, package_map, lineage, export, review_lock, *, repository_root=None):
    # Verify all input identities/truth before running either classifier.
    baseline = _load_baseline(Path(export))
    lock = json.loads(Path(review_lock).read_text(encoding='utf-8'))
    selected = reviewed_samples(baseline, lock, _hash(export))
    package_rows = json.loads(Path(package_map).read_text(encoding='utf-8'))
    intake = build_intake(package_rows, [], [])
    registry = load_concealed_template_lineage(lineage)
    issues = verify_lineage_evidence_paths(registry, repository_root or Path(__file__).resolve().parents[2])
    if issues:
        raise ValueError('lineage registry has missing or escaped review evidence')
    query = canonicalize_match_group(baseline['original_match_group'])
    source = registry.get(baseline['source']['sha256'])
    if source is not None and source.match_group != query:
        raise ValueError('query source SHA conflicts with reviewed match registry')
    from PIL import Image
    from .tiles_v0_1.labels import approved_labels
    from .tiles_v0_1.template_classifier import TemplateTileClassifier, _feature
    from .tiles_runtime_v0_2.runtime_reader import CONCEALED_IDENTITY_GATE_REGION
    labels = [row for row in approved_labels(dataset)
              if row.get('region') in {'hand_region', 'draw_region', 'draw_visual'}
              and not row.get('gold_skin_only') and row.get('tile_id') in STANDARD_TILES]
    training, selection = qualify_concealed_template_labels(labels, registry, query_match_group=query)
    hashes = {}
    for row in training:
        root = Path(dataset).resolve()
        path = (root / row['image']).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('qualified real template is missing or escapes dataset')
        digest = _hash(path)
        if row.get('asset_sha256') is not None and row['asset_sha256'] != digest:
            raise ValueError('reviewed template asset hash mismatch')
        hashes[row['image']] = digest
    primary = TemplateTileClassifier.from_labels(dataset, training) if training else None
    real = primary.regional_templates.get(CONCEALED_IDENTITY_GATE_REGION, {}) if primary else {}
    merged = {tile: list(features) for tile, features in real.items()}
    for row in package_rows:
        if row['project_tile'] not in STANDARD_TILES:
            continue
        with Image.open(row['derived_image']) as image:
            merged.setdefault(row['project_tile'], []).append(_feature(image, region='hand_region'))
    candidate = TemplateTileClassifier(merged, {CONCEALED_IDENTITY_GATE_REGION: merged})
    groups = {}
    for row in training:
        groups.setdefault(row['tile_id'], set()).add(row['_original_match_group'])
    # Artwork never fills class coverage or counts as a real independent match.
    support = {tile for tile, values in groups.items() if len(values) >= 2}
    covered = set(real)
    samples = []
    for sample in selected:
        slots, used_paths = [], set()
        for slot in sample['alignment']['slots']:
            path = private_crop_path(export, sample['sample_id'], slot.get('private_crop_ref'))
            if path in used_paths:
                raise ValueError('multiple slots reference the same query image')
            used_paths.add(path)
            with Image.open(path) as image:
                crop = image.convert('RGB')
            a = gated_prediction(primary.classify(crop, region=CONCEALED_IDENTITY_GATE_REGION) if primary else None, covered, support)
            b = gated_prediction(candidate.classify(crop, region=CONCEALED_IDENTITY_GATE_REGION), covered, support)
            # Protected candidate preserves every baseline accepted identity.
            slots.append({'slot': slot.get('slot'), 'truth_tile': slot['truth_tile'],
                          'crop_sha256': _hash(path), 'baseline': a, 'artwork_merged': b,
                          'primary_first': primary_first_prediction(a, b)})
        samples.append({'sample_id': sample['sample_id'], 'slots': slots})
    return {'schema_version': 'client_artwork_whole_hand_ab_development_v0_1',
            'status': 'DEVELOPMENT_ONLY_NOT_RUNTIME_PROMOTION', 'query_match_group': query,
            'query_group_authority': 'reviewed_registry' if source else 'private_review_lock_only',
            'source_sha256': baseline['source']['sha256'], 'confidence_threshold': THRESHOLD,
            'inputs_sha256': {'baseline_export': _hash(export), 'review_lock': _hash(review_lock),
                             'lineage_registry': _hash(lineage)},
            'verified_package_assets': intake['package_assets'], 'real_template_sha256': hashes,
            'training_selection': selection, 'real_classes_with_two_other_match_groups': sorted(support),
            'support_gate': 'real_other_original_match_groups_only; minimum_two; package_excluded',
            'metrics': {v: summarize(samples, v) for v in ('baseline', 'artwork_merged', 'primary_first')},
            'paired_raw_improvements': sum(s['baseline']['candidate'] != s['truth_tile'] and s['artwork_merged']['candidate'] == s['truth_tile'] for h in samples for s in h['slots']),
            'paired_raw_regressions': sum(s['baseline']['candidate'] == s['truth_tile'] and s['artwork_merged']['candidate'] != s['truth_tile'] for h in samples for s in h['slots']),
            'samples': samples, 'runtime_changed': False, 'formal_promotion_evidence': False,
            'safe_for_hint': False, 'safe_for_executor': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('dataset', 'package-map', 'lineage', 'baseline-export', 'review-lock', 'output'):
        parser.add_argument('--' + option, required=True)
    parser.add_argument('--repository-root')
    args = parser.parse_args()
    report = evaluate(args.dataset, args.package_map, args.lineage, args.baseline_export, args.review_lock,
                      repository_root=args.repository_root)
    with Path(args.output).open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(report['metrics'], allow_nan=False))


if __name__ == '__main__':
    main()
