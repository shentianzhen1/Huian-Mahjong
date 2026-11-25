import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from workspace.vision.client_artwork_ab import (
    evaluate, primary_first_prediction, private_crop_path, reviewed_samples, summarize,
)
from workspace.vision.development_asset_intake import CLIENT_TILES


def fixture_baseline():
    return {'schema_version': 'vision_runtime_v0_2_whole_hand_baseline_export_v0_1',
            'confidence_threshold': 0.82, 'confidence_threshold_frozen': True,
            'source': {'sha256': '9' * 64}, 'original_match_group': 'query',
            'samples': [{'sample_id': 'sample', 'truth': {'concealed_hand': ['M1'],
                'draw_visual': None, 'gold_skinned_draw': False},
                'alignment': {'status': 'exact_count_left_to_right_alignment_pending_crop_review',
                'slots': [{'slot': 0, 'region': 'hand', 'truth_tile': 'M1', 'private_crop_ref': '0.png'}]}}]}


def fixture_lock(export_hash):
    return {'schema_version': 'client_artwork_ab_review_lock_v0_1',
            'development_only': True, 'reviewed': True, 'reviewer': 'fixture',
            'baseline_export_sha256': export_hash, 'source_sha256': '9' * 64,
            'original_match_group': 'query', 'samples': [{'sample_id': 'sample', 'truth_tiles': ['M1']}]}


class ClientArtworkContractTests(unittest.TestCase):
    def test_review_lock_rejects_stale_identity_incomplete_truth_and_gold(self):
        baseline = fixture_baseline()
        lock = fixture_lock('a' * 64)
        self.assertEqual(len(reviewed_samples(baseline, lock, 'a' * 64)), 1)
        for key, bad in [('reviewed', False), ('development_only', False),
                         ('baseline_export_sha256', 'b' * 64), ('source_sha256', '0' * 64),
                         ('original_match_group', 'other'), ('reviewer', '')]:
            altered = {**lock, key: bad}
            with self.subTest(key=key), self.assertRaises(ValueError):
                reviewed_samples(baseline, altered, 'a' * 64)
        for threshold in (0.8, float('nan'), float('inf'), '0.82', True):
            with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                reviewed_samples({**baseline, 'confidence_threshold': threshold}, lock, 'a' * 64)
        for mutate in ('gold', 'missing_hand', 'duplicate_slot', 'wrong_region', 'mismatched_truth'):
            altered = copy.deepcopy(baseline)
            sample = altered['samples'][0]
            if mutate == 'gold': sample['truth']['gold_skinned_draw'] = True
            elif mutate == 'missing_hand': sample['truth']['concealed_hand'].append('M2')
            elif mutate == 'duplicate_slot': sample['alignment']['slots'].append(sample['alignment']['slots'][0])
            elif mutate == 'wrong_region': sample['alignment']['slots'][0]['region'] = 'meld'
            else: sample['alignment']['slots'][0]['truth_tile'] = 'M2'
            with self.subTest(case=mutate), self.assertRaises(ValueError):
                reviewed_samples(altered, lock, 'a' * 64)

    def test_unreviewed_export_sample_is_not_silently_added(self):
        baseline = fixture_baseline()
        baseline['samples'].append({**baseline['samples'][0], 'sample_id': 'unreviewed'})
        selected = reviewed_samples(baseline, fixture_lock('a' * 64), 'a' * 64)
        self.assertEqual([s['sample_id'] for s in selected], ['sample'])

    def test_private_query_paths_cannot_escape_or_be_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            crop = root / 'crops/sample/0.png'
            crop.parent.mkdir(parents=True)
            crop.write_bytes(b'fixture')
            export = root / 'baseline.json'
            self.assertEqual(private_crop_path(export, 'sample', '0.png'), crop)
            for sample, ref in [('sample', '../../outside.png'), ('../../', 'outside.png'),
                                ('sample', '../other/0.png'), ('sample', 'missing.png')]:
                with self.subTest(sample=sample, ref=ref), self.assertRaises(ValueError):
                    private_crop_path(export, sample, ref)

    def test_primary_accepts_are_preserved_without_mutating_predictions(self):
        a = {'candidate': 'M1', 'accepted': 'M1'}
        b = {'candidate': 'M2', 'accepted': 'M2'}
        result = primary_first_prediction(a, b)
        self.assertEqual(result['accepted'], 'M1')
        result['accepted'] = 'M3'
        self.assertEqual(a['accepted'], 'M1')
        self.assertEqual(primary_first_prediction({**a, 'accepted': 'UNKNOWN'}, b), b)

    def test_whole_hand_metrics_separate_correct_wrong_and_blocked(self):
        def slot(truth, raw, accepted):
            return {'truth_tile': truth, 'v': {'candidate': raw, 'accepted': accepted, 'reason': 'test'}}
        samples = [{'slots': [slot('M1', 'M1', 'M1')]},
                   {'slots': [slot('M1', 'M2', 'M2')]},
                   {'slots': [slot('M1', 'M1', 'UNKNOWN')]}]
        metrics = summarize(samples, 'v')
        self.assertEqual((metrics['raw_correct'], metrics['accepted_correct'], metrics['wrong_accepted'], metrics['rejected']), (2, 1, 1, 1))
        self.assertEqual((metrics['exact_raw_hands'], metrics['exact_accepted_hands'], metrics['fully_accepted_wrong_hands']), (2, 1, 1))


@unittest.skipUnless(importlib.util.find_spec('cv2'), 'Vision dependency required')
class ClientArtworkImageTests(unittest.TestCase):
    def test_verified_image_ab_does_not_count_artwork_as_real_support(self):
        from PIL import Image
        import numpy as np

        def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = []
            atlas = root / 'atlas.bin'; atlas.write_bytes(b'fixture atlas')
            metadata = root / 'sprites.json'; metadata.write_text('{}')
            for identifier, tile in enumerate(CLIENT_TILES):
                pixels = np.full((60, 40, 3), 245, dtype=np.uint8)
                pattern = np.random.default_rng(identifier).integers(0, 2, (10, 8)) * 230
                pixels[15:45, 8:32] = np.repeat(np.repeat(pattern, 3, 0), 3, 1)[..., None]
                path = root / (tile + '.png'); Image.fromarray(pixels).save(path)
                package.append({'client_id': identifier, 'project_tile': tile, 'derived_image': str(path),
                    'derived_sha256': sha(path), 'atlas': str(atlas), 'atlas_sha256': sha(atlas),
                    'metadata': str(metadata), 'metadata_sha256': sha(metadata), 'runtime_admission': False})
            package_map = root / 'map.json'; package_map.write_text(json.dumps(package))
            dataset = root / 'dataset'; (dataset / 'templates').mkdir(parents=True)
            (dataset / 'templates/M1.png').write_bytes((root / 'M1.png').read_bytes())
            labels = [{'approved': True, 'tile_id': 'M1', 'region': 'hand_region',
                'source_session': 's' + str(i), 'sha256': digit * 64,
                'image': 'templates/M1.png', 'bbox': [0, 0, 40, 60]} for i, digit in enumerate(('a', 'b'))]
            (dataset / 'labels.jsonl').write_text('\n'.join(map(json.dumps, labels)))
            (root / 'review.md').write_text('synthetic fixture only')
            registry = root / 'lineage.json'; registry.write_text(json.dumps({
                'schema_version': 'concealed_template_match_lineage_development_v0_1',
                'development_only': True, 'excluded_from_formal_promotion': True,
                'sources': [{'source_sha256': digit * 64, 'match_group': group, 'evidence_path': 'review.md'}
                    for digit, group in [('a', 'support1'), ('b', 'support2'), ('9', 'query')]]}))
            export = root / 'baseline.json'; export.write_text(json.dumps(fixture_baseline()))
            crop = root / 'crops/sample/0.png'; crop.parent.mkdir(parents=True)
            crop.write_bytes((root / 'M1.png').read_bytes())
            lock = root / 'lock.json'; lock.write_text(json.dumps(fixture_lock(sha(export))))
            report = evaluate(dataset, package_map, registry, export, lock, repository_root=root)
            self.assertEqual(len(report['verified_package_assets']), 42)
            self.assertEqual(report['real_classes_with_two_other_match_groups'], ['M1'])
            self.assertEqual(report['metrics']['artwork_merged']['accepted'], 0)
            self.assertEqual(report['metrics']['baseline']['raw_correct'], 1)
            self.assertEqual(report['metrics']['primary_first']['raw_correct'], 1)
            self.assertFalse(report['runtime_changed'])
            self.assertFalse(report['safe_for_hint'])
            self.assertFalse(report['safe_for_executor'])
            self.assertNotIn(str(root), json.dumps(report))
