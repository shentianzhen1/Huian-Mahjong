import unittest

from workspace.vision.concealed_template_match_lineage import ConcealedTemplateSource
from workspace.vision.tiles_runtime_v0_2.sampled_replay_classifier_ab import select_rows, summarize


class SampledReplayClassifierTests(unittest.TestCase):
    def test_unknown_lineage_does_not_block_development_training(self):
        labels = [dict(tile_id='S6', region='hand_region', sha256='a'),
                  dict(tile_id='G', region='hand_region', sha256='b')]
        rows, report = select_rows(labels, {}, set(), set())
        self.assertEqual(len(rows), 2)
        self.assertEqual(report['unresolved_lineage_available'], 2)
        strict, _ = select_rows(labels, {}, set(), set(), reviewed_only=True)
        self.assertEqual(strict, [])

    def test_exact_query_and_known_same_match_are_excluded(self):
        lineage = {'a': ConcealedTemplateSource('a', 'query-match', 'evidence')}
        labels = [dict(tile_id='S6', region='hand_region', sha256='a'),
                  dict(tile_id='G', region='hand_region', sha256='b'),
                  dict(tile_id='P2', region='hand_region', sha256='c')]
        rows, report = select_rows(labels, lineage, {'b'}, {'query-match'})
        self.assertEqual([r['tile_id'] for r in rows], ['P2'])
        self.assertEqual(report['excluded_query_source_or_known_match'], 2)

    def test_wrong_tile_breaks_whole_hand_and_gold_scored_separately(self):
        rows = [dict(sample_id='one', role='concealed', truth='S6', model='S4'),
                dict(sample_id='one', role='concealed', truth='G', model='G'),
                dict(sample_id='two', role='concealed', truth='P2', model='P2'),
                dict(sample_id='two', role='opened_gold', truth='M4', model='M1')]
        result = summarize(rows, 'model')
        self.assertEqual(result['whole_hand_exact'], 1)
        self.assertEqual(result['hands'], 2)
        self.assertEqual(result['concealed_correct'], 2)
        self.assertEqual(result['opened_gold_correct'], 0)
        self.assertEqual(result['concealed_confusions'], {'S6->S4': 1})

    def test_known_bad_long_clip_truth_does_not_return(self):
        import json
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        truth = json.loads((root / 'references/vision/2026-10-24/long_clip_reviewed_sample_truth_v0_1.json').read_text())
        for frame in truth['frames']:
            with self.subTest(frame=frame['frame_index']):
                self.assertIn('S4', frame['own_hand'])
                self.assertIn('S8', frame['own_hand'])
                self.assertNotIn('S6', frame['own_hand'])
                self.assertNotIn('G', frame['own_hand'])
        self.assertEqual(len(truth['frames']), 6)
