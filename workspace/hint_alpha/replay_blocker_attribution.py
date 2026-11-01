"""Offline truth interventions on replay snapshots; never automatic acceptance.

Run with --replay and --truth JSON files. Truth must pin every eligible sampled
frame's RGB hash and complete hand; no interpolation across unreviewed frames.
Geometry, melds, source scope and physical validation remain machine outputs.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path

from huian._legacy import env
from .current_snapshot_advisor import analyze_snapshot_shanten
from workspace.vision.current_state_snapshot import CurrentTableSnapshot

MODES = ('machine', 'gold_only', 'hand_only', 'gold_and_hand')


def attribute_replay(replay, truth):
    if not replay.get('source_sha256') or replay['source_sha256'] != truth['source_sha256']:
        raise ValueError('Truth/replay source SHA mismatch')
    if replay.get('advice_mode') != 'stateless':
        raise ValueError('Attribution requires stateless replay snapshots')
    if truth.get('review_authority') != 'ASSISTANT_REVIEWED_REVEALED_DEVELOPMENT':
        raise ValueError('Require explicit revealed-development review authority')
    entries = truth['frames']
    if len({e['frame_index'] for e in entries}) != len(entries):
        raise ValueError('Duplicate truth frame')
    by_frame = {e['frame_index']: e for e in entries}
    rows, excluded = [], []
    for row in replay['rows']:
        ids, hashes = row['frames'], row['pixel_sha256']
        if len(ids) != 3 or len(set(ids)) != 3 or ids != sorted(ids) or len(hashes) != 3:
            raise ValueError('Require three distinct hashed frames')
        reviewed = [by_frame.get(i) for i in ids]
        if any(e is None for e in reviewed):
            excluded.append({'frames': ids, 'reason': 'incomplete_sampled_frame_truth'})
            continue
        for e, digest in zip(reviewed, hashes):
            if e['rgb_sha256'] != digest:
                raise ValueError('Truth/replay frame RGB SHA mismatch')
            if (e['gold_tile'] not in env.BASE_TILES or not e['own_hand']
                    or any(t not in env.BASE_TILES for t in e['own_hand'])):
                raise ValueError('Invalid truth tile')
        signatures = {(tuple(e['own_hand']), e['gold_tile']) for e in reviewed}
        if len(signatures) != 1:
            excluded.append({'frames': ids, 'reason': 'truth_changes_within_burst'})
            continue
        if type(row.get('geometry_untrusted')) is not bool:
            raise ValueError('Explicit geometry trust flag required; rerun replay')
        raw = dict(row['snapshot'])
        raw['own_hand'] = tuple(raw['own_hand'])
        raw['melds'] = tuple(tuple(tuple(g) for g in seat) for seat in raw['melds'])
        snapshot = CurrentTableSnapshot(**raw)
        if snapshot.source_session != replay['session']:
            raise ValueError('Snapshot/replay source session mismatch')
        hand, gold = next(iter(signatures))
        components = row.get('identity_observations', {}).get('components', [])
        concealed = [c for c in components
                     if c.get('region_candidate') in ('hand', 'draw_visual')]
        candidates = Counter(c.get('candidate_tile_id') for c in concealed)
        expected = Counter(hand)
        candidate_diagnostic = None if not concealed else {
            'whole_hand_exact': candidates == expected,
            'missing_true_tiles': dict(expected - candidates),
            'extra_candidate_tiles': dict(candidates - expected),
            'rejected_candidates': [
                {k: c.get(k) for k in ('candidate_tile_id', 'identity_reason', 'tile_confidence')}
                for c in concealed if c.get('identity_reason') != 'accepted'],
        }
        decisions = {}
        for mode in MODES:
            updates = {}
            if mode in ('gold_only', 'gold_and_hand'):
                updates.update(gold_tile=gold, gold_trusted=not row['geometry_untrusted'])
            if mode in ('hand_only', 'gold_and_hand'):
                updates.update(own_hand=hand, hand_trusted=not row['geometry_untrusted'])
            hint = analyze_snapshot_shanten(replace(snapshot, **updates))
            decisions[mode] = {'calculation_allowed': hint.allowed,
                               'shanten': hint.shanten, 'phase': hint.phase,
                               'gate_issues': [issue for issue in hint.issues
                                               if issue not in snapshot.adapter_issues]}
        if decisions['machine']['calculation_allowed'] != row['hint']['allowed']:
            raise ValueError('Machine hint changed on replay; pin code and inputs')
        rows.append({'frames': ids, 'geometry_untrusted': row['geometry_untrusted'],
                     'machine_hand_exact': Counter(snapshot.own_hand) == Counter(hand),
                     'original_adapter_issues': list(snapshot.adapter_issues),
                     'candidate_diagnostic': candidate_diagnostic,
                     'decisions': decisions})
    return {'schema_version': 'replay_blocker_attribution_v0_1',
            'source_sha256': replay['source_sha256'],
            'development_only': True, 'formal_promotion_evidence': False,
            'automatic_acceptance_claim': False, 'safe_for_executor': False,
            'scope': 'snapshot_intervention_not_classifier_or_stateful_repair',
            'comparable_windows': len(rows), 'excluded_windows': excluded,
            'calculation_allowed_windows': {mode: sum(
                r['decisions'][mode]['calculation_allowed'] for r in rows) for mode in MODES},
            'rows': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replay', type=Path, required=True)
    parser.add_argument('--truth', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = attribute_replay(json.loads(args.replay.read_text()),
                              json.loads(args.truth.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}))


if __name__ == '__main__':
    main()
