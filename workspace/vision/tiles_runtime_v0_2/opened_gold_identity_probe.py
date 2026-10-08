"""Offline opened-indicator appearance and exact-source leakage diagnostic.

Uses unchanged Gold features on the actual exported detector crop. Scores are
ranking diagnostics, never Runtime acceptance, and exact-SHA filtering is not
proof of original-match independence. No candidate is connected to Hint/UI.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

FROZEN_THRESHOLD = 0.82


def summarize_match_disjoint_examples(examples, *, expected_tile, source_sha,
                                     query_match_group, lineage):
    """Exclude unknown lineage and every template from the query match.

    The query group comes from the reviewed export, not its session name.
    This is a development ranking audit, not an accuracy/promotion gate.
    """
    from workspace.vision.concealed_template_match_lineage import (
        qualify_concealed_template_labels,
    )
    query_source = lineage.get(source_sha)
    if query_source is not None and query_source.match_group != query_match_group:
        raise ValueError('query original-match group conflicts with reviewed SHA lineage')
    rows = [dict(row, sha256=row.get('source_sha256')) for row in examples]
    qualified, audit = qualify_concealed_template_labels(
        rows, lineage, query_match_group=query_match_group)
    result = summarize_examples(qualified, expected_tile=expected_tile,
                                excluded_source_shas=[source_sha])
    result['lineage_audit'] = audit
    result['filter_scope'] = 'reviewed_exact_SHA_original_match_disjoint_bank'
    result['original_match_disjointness_established'] = bool(qualified)
    result['formal_promotion_evidence'] = False
    return result


def summarize_examples(examples, *, expected_tile, excluded_source_shas=()):
    excluded = set(excluded_source_shas)
    winners = {}
    skipped = 0
    for row in examples:
        if row.get('source_sha256') in excluded:
            continue
        score = row.get('score')
        if (isinstance(score, bool) or not isinstance(score, (int, float))
                or not math.isfinite(score) or row.get('feature_degenerate') is True):
            skipped += 1
            continue
        tile = row['tile_id']
        if tile not in winners or score > winners[tile]['score']:
            winners[tile] = dict(row)
    ranked = sorted(winners.values(), key=lambda row: (-row['score'], row['tile_id']))
    return {
        'expected_tile': expected_tile,
        'candidate_tile': ranked[0]['tile_id'] if ranked else None,
        'candidate_score': ranked[0]['score'] if ranked else None,
        'expected_class_rank': next((i + 1 for i, row in enumerate(ranked)
                                     if row['tile_id'] == expected_tile), None),
        'expected_class_winner': winners.get(expected_tile),
        'top_classes': ranked[:5],
        'invalid_or_degenerate_examples_skipped': skipped,
        'excluded_source_sha256': sorted(excluded),
        'runtime_threshold_reference': FROZEN_THRESHOLD,
        'scores_are_runtime_acceptance': False,
        'original_match_disjointness_established': False,
        'safe_for_runtime': False,
        'safe_for_hint': False,
        'safe_for_executor': False,
    }


def probe_export(export_path, dataset_root, *, expected_tile, lineage_path=None,
                 repository_root=None):
    import cv2
    import numpy as np
    from PIL import Image
    from workspace.vision.tiles_v0_1.labels import approved_labels
    from workspace.vision.tiles_v0_1.template_classifier import _feature, _tile_face_box

    export_path, dataset_root = Path(export_path), Path(dataset_root)
    export = json.loads(export_path.read_text(encoding='utf-8'))
    source_sha = export['source']['sha256']
    lineage = None
    if lineage_path is not None:
        from workspace.vision.concealed_template_match_lineage import (
            load_concealed_template_lineage, verify_lineage_evidence_paths,
        )
        if repository_root is None:
            raise ValueError('repository_root is required to verify lineage evidence paths')
        lineage = load_concealed_template_lineage(lineage_path)
        issues = verify_lineage_evidence_paths(lineage, repository_root)
        if issues:
            raise ValueError(f'lineage evidence paths failed verification: {issues}')
    labels = approved_labels(dataset_root)
    bank = []
    for label in labels:
        path = dataset_root / label['image']
        if not path.is_file():
            continue
        with Image.open(path) as source:
            crop = source.convert('RGB')
            if Path(label['image']).parts[:1] != ('templates',):
                x, y, width, height = label['bbox']
                crop = crop.crop((x, y, x + width, y + height))
            feature = _feature(crop, region='gold_region')
        bank.append((label, feature))

    samples = []
    for sample in export['samples']:
        indicators = [c for c in sample['components'] if c['region_candidate'] == 'gold']
        if len(indicators) != 1:
            samples.append({'timestamp_seconds': sample['timestamp_seconds'],
                            'status': 'EXPLICIT_INDICATOR_COUNT_NOT_ONE'})
            continue
        component = indicators[0]
        reference = component.get('private_crop_ref')
        if not reference:
            raise ValueError('export must contain the actual detector classification crop')
        crop_root = (export_path.parent / 'crops' / sample['sample_id']).resolve()
        crop_path = (crop_root / reference).resolve()
        crop_path.relative_to(crop_root)
        with Image.open(crop_path) as source:
            crop = source.convert('RGB')
            query = _feature(crop, region='gold_region')
            query_size = list(crop.size)
            face_box = _tile_face_box(crop)
        examples = []
        query_degenerate = float(np.std(query)) < 1e-6
        for label, feature in bank:
            degenerate = query_degenerate or float(np.std(feature)) < 1e-6
            score = None if degenerate else float(cv2.matchTemplate(
                query, feature, cv2.TM_CCOEFF_NORMED)[0, 0])
            examples.append({'tile_id': label['tile_id'], 'image': label['image'],
                             'source_sha256': label.get('sha256'),
                             'source_session': label.get('source_session'),
                             'source_region': label.get('region'),
                             'gold_skin_only': bool(label.get('gold_skin_only')),
                             'feature_degenerate': degenerate, 'score': score})
        result = {'timestamp_seconds': sample['timestamp_seconds'],
                        'status': 'SCORED_DETECTOR_CROP',
                        'pixel_bbox': component['pixel_bbox'],
                        'classification_crop_bbox': component['classification_crop_bbox'],
                        'query_size': query_size, 'query_bright_face_bbox': face_box,
                        'current_runtime_identity': {
                            key: component.get(key) for key in (
                                'candidate_tile_id', 'tile_id', 'tile_confidence',
                                'identity_reason')},
                        'current_bank': summarize_examples(examples, expected_tile=expected_tile),
                        'exact_source_filtered': summarize_examples(examples,
                            expected_tile=expected_tile, excluded_source_shas=[source_sha])}
        if lineage is not None:
            result['reviewed_match_disjoint'] = summarize_match_disjoint_examples(
                examples, expected_tile=expected_tile, source_sha=source_sha,
                query_match_group=export['original_match_group'], lineage=lineage)
        samples.append(result)
    return {'schema_version': 'opened_gold_identity_probe_v0_1',
            'status': 'DEVELOPMENT_APPEARANCE_DIAGNOSTIC',
            'source_sha256': source_sha,
            'original_match_group': export['original_match_group'],
            'expected_opened_tile': expected_tile,
            'expected_identity_authority': 'caller_direct_visible_indicator_review',
            'feature_path': 'unchanged _feature(region=gold_region)',
            'reviewed_match_disjoint_filter_requested': lineage is not None,
            'source_session_is_independence_signal': False,
            'raw_or_derived_pixels_in_report': False,
            'runtime_changed': False, 'threshold_changed': False,
            'formal_promotion_evidence': False,
            'safe_for_hint': False, 'safe_for_executor': False, 'samples': samples}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline_export', type=Path)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--expected-tile', required=True,
                        help='Explicit direct visual review; never inferred from a hand tile')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--lineage', type=Path,
                        help='Optional reviewed development SHA-to-original-match registry')
    parser.add_argument('--repository-root', type=Path,
                        help='Required with --lineage to verify its evidence paths')
    args = parser.parse_args()
    if args.lineage is not None and args.repository_root is None:
        parser.error('--repository-root is required with --lineage')
    report = probe_export(args.baseline_export, args.dataset, expected_tile=args.expected_tile,
                          lineage_path=args.lineage, repository_root=args.repository_root)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f"Opened-Gold diagnostic: {len(report['samples'])} checkpoints; no Runtime changes")


if __name__ == '__main__':
    main()
