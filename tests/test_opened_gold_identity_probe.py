import unittest
from workspace.vision.tiles_runtime_v0_2.opened_gold_identity_probe import summarize_examples


class OpenedGoldProbeTests(unittest.TestCase):
    def test_same_source_winner_cannot_survive_exact_sha_exclusion(self):
        rows = [{'tile_id': 'M6', 'score': .9, 'source_sha256': 'query'},
                {'tile_id': 'M7', 'score': .3, 'source_sha256': 'other'},
                {'tile_id': 'M6', 'score': .2, 'source_sha256': 'other'}]
        result = summarize_examples(rows, expected_tile='M6', excluded_source_shas=['query'])
        self.assertEqual(result['candidate_tile'], 'M7')
        self.assertEqual(result['expected_class_rank'], 2)
        self.assertEqual(result['expected_class_winner']['source_sha256'], 'other')
        self.assertFalse(result['original_match_disjointness_established'])
        self.assertFalse(result['scores_are_runtime_acceptance'])
        self.assertFalse(result['safe_for_runtime'])

    def test_nonfinite_and_constant_ncc_candidates_are_not_ranked(self):
        rows = [{'tile_id': 'M1', 'score': float('nan')},
                {'tile_id': 'M2', 'score': float('inf')},
                {'tile_id': 'M3', 'score': 1., 'feature_degenerate': True},
                {'tile_id': 'M6', 'score': .3}]
        result = summarize_examples(rows, expected_tile='M6')
        self.assertEqual(result['candidate_tile'], 'M6')
        self.assertEqual(result['invalid_or_degenerate_examples_skipped'], 3)
