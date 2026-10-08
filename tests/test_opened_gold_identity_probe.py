import unittest
from workspace.vision.tiles_runtime_v0_2.opened_gold_identity_probe import (
    summarize_examples, summarize_match_disjoint_examples,
)
from workspace.vision.concealed_template_match_lineage import ConcealedTemplateSource


class OpenedGoldProbeTests(unittest.TestCase):
    def test_match_filter_excludes_other_clip_and_unknown_lineage(self):
        query, adjacent, independent, unknown = [c * 64 for c in 'abcd']
        lineage = {
            query: ConcealedTemplateSource(query, 'match-a', 'evidence.json'),
            adjacent: ConcealedTemplateSource(adjacent, 'match-a', 'evidence.json'),
            independent: ConcealedTemplateSource(independent, 'match-b', 'evidence.json'),
        }
        rows = [{'tile_id': 'M6', 'score': .99, 'source_sha256': adjacent,
                 'source_session': 'different_clip_session'},
                {'tile_id': 'M6', 'score': .98, 'source_sha256': unknown,
                 'source_session': 'apparently_unique'},
                {'tile_id': 'M7', 'score': .3, 'source_sha256': independent}]
        result = summarize_match_disjoint_examples(
            rows, expected_tile='M6', source_sha=query,
            query_match_group='match-a', lineage=lineage)
        self.assertEqual(result['candidate_tile'], 'M7')
        self.assertIsNone(result['expected_class_winner'])
        self.assertEqual(result['lineage_audit']['excluded_same_original_match_count'], 1)
        self.assertEqual(result['lineage_audit']['excluded_missing_original_match_lineage_count'], 1)
        self.assertTrue(result['original_match_disjointness_established'])
        self.assertFalse(result['formal_promotion_evidence'])
        self.assertFalse(result['safe_for_hint'])

    def test_conflicting_query_group_fails_closed(self):
        query = 'a' * 64
        lineage = {query: ConcealedTemplateSource(query, 'match-a', 'evidence.json')}
        with self.assertRaisesRegex(ValueError, 'conflicts'):
            summarize_match_disjoint_examples(
                [], expected_tile='M6', source_sha=query,
                query_match_group='match-b', lineage=lineage)

    def test_empty_qualified_bank_is_not_independence_evidence(self):
        result = summarize_match_disjoint_examples(
            [{'tile_id': 'M6', 'score': .99, 'source_sha256': 'b' * 64}],
            expected_tile='M6', source_sha='a' * 64,
            query_match_group='match-a', lineage={})
        self.assertIsNone(result['candidate_tile'])
        self.assertFalse(result['original_match_disjointness_established'])

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
