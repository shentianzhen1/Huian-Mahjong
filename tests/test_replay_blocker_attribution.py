import copy
import unittest
from dataclasses import asdict

from workspace.hint_alpha.current_snapshot_advisor import analyze_snapshot_shanten
from workspace.hint_alpha.replay_blocker_attribution import attribute_replay
from workspace.vision.current_state_snapshot import CurrentTableSnapshot


class AttributionTests(unittest.TestCase):
    def setUp(self):
        self.hand = ('M6','P3','P4','P5','P6','P6','P6','P7','P7','P8','P9','P9','S2','S2','S5','S5')
        snapshot = CurrentTableSnapshot(0.4, 'source', 0, 3, (None,)*16,
            None, ((),()), ((),()), False, False, (False,False), (True,False))
        self.replay = {'source_sha256': 'a'*64, 'session': 'source', 'advice_mode': 'stateless',
            'rows': [{'frames': [0,6,12], 'pixel_sha256': ['b'*64]*3,
                      'geometry_untrusted': False, 'snapshot': asdict(snapshot),
                      'hint': asdict(analyze_snapshot_shanten(snapshot))}]}
        self.truth = {'source_sha256': 'a'*64,
            'review_authority': 'ASSISTANT_REVIEWED_REVEALED_DEVELOPMENT',
            'frames': [{'frame_index': f, 'rgb_sha256': 'b'*64,
                        'own_hand': list(self.hand), 'gold_tile': 'M6'} for f in (0,6,12)]}

    def test_interventions_separate_blockers_and_do_not_mutate_inputs(self):
        before = copy.deepcopy(self.replay)
        result = attribute_replay(self.replay, self.truth)
        self.assertEqual(result['calculation_allowed_windows'],
                         dict(machine=0, gold_only=0, hand_only=0, gold_and_hand=1))
        self.assertEqual(self.replay, before)
        self.assertFalse(result['automatic_acceptance_claim'])

    def test_geometry_and_meld_blocks_remain(self):
        for kind in ('geometry', 'meld'):
            with self.subTest(kind=kind):
                replay = copy.deepcopy(self.replay)
                if kind == 'geometry':
                    replay['rows'][0]['geometry_untrusted'] = True
                else:
                    replay['rows'][0]['snapshot']['meld_trusted'] = (False, False)
                self.assertEqual(attribute_replay(replay, self.truth)
                                 ['calculation_allowed_windows']['gold_and_hand'], 0)

    def test_no_carry_across_missing_or_changed_truth(self):
        for kind in ('missing', 'changed'):
            with self.subTest(kind=kind):
                truth = copy.deepcopy(self.truth)
                if kind == 'missing':
                    truth['frames'].pop()
                else:
                    truth['frames'][-1]['own_hand'].append('M3')
                result = attribute_replay(self.replay, truth)
                self.assertEqual(result['comparable_windows'], 0)
                self.assertEqual(len(result['excluded_windows']), 1)

    def test_mismatches_and_stateful_inputs_rejected(self):
        for kind in ('source', 'pixels', 'session', 'stateful', 'geometry_missing'):
            with self.subTest(kind=kind):
                replay, truth = copy.deepcopy(self.replay), copy.deepcopy(self.truth)
                if kind == 'source': truth['source_sha256'] = 'c'*64
                if kind == 'pixels': truth['frames'][0]['rgb_sha256'] = 'c'*64
                if kind == 'session': replay['session'] = 'other'
                if kind == 'stateful': replay['advice_mode'] = 'stateful'
                if kind == 'geometry_missing': replay['rows'][0].pop('geometry_untrusted')
                with self.assertRaises(ValueError): attribute_replay(replay, truth)

    def test_physical_overflow_still_blocks(self):
        for e in self.truth['frames']:
            e['own_hand'] = ['P6']*16
        result = attribute_replay(self.replay, self.truth)
        self.assertEqual(result['calculation_allowed_windows']['gold_and_hand'], 0)
        self.assertIn('physical_copy_overflow:P6', result['rows'][0]['decisions']['gold_and_hand']['gate_issues'])

    def test_candidate_ranking_separate_from_trusted_hand(self):
        row = self.replay['rows'][0]
        row['identity_observations'] = {'components': [
            dict(region_candidate='hand', candidate_tile_id=t,
                 identity_reason='below_confidence_threshold', tile_confidence=0.5)
            for t in self.hand]}
        result = attribute_replay(self.replay, self.truth)
        self.assertTrue(result['rows'][0]['candidate_diagnostic']['whole_hand_exact'])
        self.assertFalse(result['rows'][0]['machine_hand_exact'])
        row['identity_observations']['components'][0]['candidate_tile_id'] = 'S4'
        diagnostic = attribute_replay(self.replay, self.truth)['rows'][0]['candidate_diagnostic']
        self.assertEqual(diagnostic['missing_true_tiles'], {'M6': 1})
        self.assertEqual(diagnostic['extra_candidate_tiles'], {'S4': 1})
