import json
from copy import deepcopy
from pathlib import Path
import unittest
from workspace.hint_alpha.theoretical_discards import explain_theoretical_discards

class TheoreticalDiscardTests(unittest.TestCase):
    def test_frozen_reviewed_hands_match_offline_probe_without_changing_hint(self):
        root=Path(__file__).resolve().parents[1]/'references/vision/2026-10-25'
        hands=json.loads((root/'first_draw_endpoint_review_20261029.development.json').read_text())['rows']
        probe=json.loads((root/'theoretical_candidate_types_20261029.development.json').read_text())['rows']
        expected={r['frame']:r for r in probe}
        for review in hands:
            row={'display_allowed': True,'snapshot':{'own_hand':review['reviewed_hand'],'gold_tile':'M4','melds':[[[None]*4]*review['reviewed_own_meld_count'],[]]},'hint':{'phase':'POST_DRAW','best_discards':[{'discard':d} for d in review['structural_discards']]}}
            original=deepcopy(row)
            result=explain_theoretical_discards(row)
            self.assertEqual(row,original)
            self.assertTrue(result['remaining_copies_unknown'])
            self.assertFalse(result['strategy_ranking'])
            self.assertFalse(result['safe_for_executor'])
            self.assertEqual([(c['discard'],c['theoretical_effective_types']) for c in result['candidates']],[(c['discard'],c['theoretical_effective_types']) for c in expected[review['frame']]['candidates']])
    def test_blocked_or_pre_draw_has_no_discard_explanation(self):
        for row in ({'display_allowed':False},{'display_allowed':True,'hint':{'phase':'PRE_DRAW'}}):
            self.assertIsNone(explain_theoretical_discards(row))
