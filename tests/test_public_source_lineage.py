"""Prevent same-match clip leakage and previously-inspected holdout promotion."""
from __future__ import annotations
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from dataclasses import replace
from workspace.vision.public_source_lineage import (
    compare_sources, development_lineage_report, load_lineage, verify_local_source,
)

REGISTRY = Path(__file__).resolve().parents[1] / 'references/vision/2026-09-23/public_source_lineage.development.json'

class PublicSourceLineageTests(unittest.TestCase):
    def test_two_hands_same_match_distinct_bytes(self):
        d = load_lineage(REGISTRY)
        pair = compare_sources(d['match_evidence_001_hand_01'], d['match_evidence_001_hand_02'])
        self.assertTrue(pair['different_video_bytes'])
        self.assertFalse(pair['different_recorded_match'])
        self.assertFalse(pair['formal_promotion_eligible'])

    def test_archived_distinct_match_is_still_not_formal_holdout(self):
        d = load_lineage(REGISTRY)
        pair = compare_sources(d['match_evidence_001_hand_02'], d['archived_replay_separate_match_001'])
        self.assertTrue(pair['different_recorded_match'])
        self.assertFalse(pair['formal_promotion_eligible'])
        self.assertEqual(development_lineage_report(REGISTRY)['distinct_recorded_matches'], 2)
        self.assertEqual(development_lineage_report(REGISTRY)['formal_promotion_eligible_clips'], 0)

    def test_hash_mismatch_refuses_source_data(self):
        d = load_lineage(REGISTRY)
        with TemporaryDirectory() as td:
            path = Path(td)/'fake.mp4'
            path.write_bytes(b'not the archived replay')
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                verify_local_source(path, d['archived_replay_separate_match_001'])

    def test_conflicting_match_groups_and_unsafe_promotion_rejected(self):
        d = json.loads(REGISTRY.read_text())
        d['sources'][1]['match_group'] = 'fake_different_match'
        d['sources'][1]['source_sha256'] = d['sources'][0]['source_sha256']
        with TemporaryDirectory() as td:
            path = Path(td)/'registry.json'
            path.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError, 'conflicting match groups'):
                load_lineage(path)
        original=load_lineage(REGISTRY)['match_evidence_001_hand_01']
        with self.assertRaisesRegex(ValueError,'cannot certify promotion'):
            replace(original, excluded_from_formal_promotion=False)

if __name__ == '__main__': unittest.main()
