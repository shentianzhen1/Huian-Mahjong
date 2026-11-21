"""Diagnostic counts must not turn public-identity gaps into shanten gates."""
from copy import deepcopy
import unittest

from tests.test_short_hand_shanten_contract import short_snapshot
from workspace.hint_alpha.current_snapshot_advisor import analyze_snapshot_shanten
from workspace.hint_alpha.replay_smoke import summarize_windows
from workspace.hint_alpha.user_guidance import format_advice_blockers


def row(index, *, allowed=False, issues=(), **kwargs):
    return dict(frames=[index, index+1, index+2], source_seconds=[0., .2, .4],
                display_allowed=allowed, hint={'issues': list(issues)}, **kwargs)


class ReplayAdviceBlockerTests(unittest.TestCase):
    def test_public_identity_gaps_are_context_even_when_shanten_is_available(self):
        hint = analyze_snapshot_shanten(short_snapshot())
        self.assertTrue(hint.allowed)
        public_issues = ['river_untrusted:0', 'opponent_meld_missing']
        rows = [row(1, allowed=True, issues=hint.issues),
                row(4, geometry_untrusted=True, issues=public_issues + ['hand_untrusted'])]
        result = summarize_windows(rows)
        self.assertEqual(result['structural_blocker_windows'], {'geometry': 1})
        self.assertEqual(result['public_context_issue_windows']['river_untrusted:0'], 2)
        # Preserve the old raw issue field for historic report compatibility.
        self.assertEqual(result['rejection_issue_windows']['river_untrusted:0'], 1)

    def test_each_blocked_window_has_one_primary_category(self):
        rows = [
            row(1, hand_boundary_pending=True, geometry_untrusted=True,
                issues=['hand_untrusted', 'gold_untrusted']),
            row(4, geometry_untrusted=True, issues=['hand_untrusted']),
            row(7, issues=['live_hand_meld_waiting_confirmation', 'hand_untrusted']),
            row(10, issues=['hand_untrusted', 'hand_identity_unknown']),
        ]
        before = deepcopy(rows)
        result = summarize_windows(rows)
        self.assertEqual(result['structural_blocker_windows'],
                         {'hand_boundary': 1, 'geometry': 1, 'stability': 1, 'hand_identity': 1})
        self.assertEqual(sum(result['structural_blocker_windows'].values()), 4)
        self.assertEqual(rows, before)

    def test_secondary_input_issues_include_overlap_and_keep_counts_distinct(self):
        rows = [
            row(1, geometry_untrusted=True, issues=[
                'hand_untrusted', 'hand_identity_unknown', 'gold_untrusted',
                'player_meld_count_untrusted', 'meld_identity_unknown:0',
            ]),
            row(4, issues=['concealed_hand_count_invalid']),
            row(7, allowed=True, issues=['opponent_meld_missing']),
        ]
        result = summarize_windows(rows)
        self.assertEqual(result['structural_blocker_windows'], {'geometry': 1, 'meld_count': 1})
        self.assertEqual(result['blocked_window_input_issues'], {
            'hand_identity': 1, 'gold': 1, 'meld_count': 1, 'concealed_hand_count': 1,
        })
        self.assertEqual(result['blocked_window_input_issue_combinations'], {
            'hand_identity+gold+meld_count': 1,
        })

    def test_hand_stages_keep_missing_evidence_and_unconfirmed_identity_distinct(self):
        issues = ['hand_untrusted']
        unknown = {'region_candidate': 'draw_visual', 'tile_id': 'UNKNOWN'}
        labeled = {'region_candidate': 'hand', 'tile_id': 'M1'}
        rows = [
            row(1, issues=issues, geometry_untrusted=True),
            row(4, issues=issues),
            row(7, issues=issues, identity_observations={'components': []}),
            row(10, issues=issues, identity_observations={'components': [labeled, unknown]}),
            row(13, issues=['concealed_hand_count_invalid'],
                identity_observations={'components': [labeled]}),
        ]
        self.assertEqual(summarize_windows(rows)['blocked_hand_stage_windows'], {
            'geometry_untrusted': 1,
            'component_evidence_missing': 1,
            'no_concealed_components_reported': 1,
            'concealed_component_identity_unconfirmed': 1,
            'concealed_components_labeled_hand_still_blocked': 1,
        })

    def test_policy_and_physical_conflicts_are_not_called_recognition_failures(self):
        policy = row(1)
        policy['hint']['allowed'] = True
        result = summarize_windows([policy, row(4, issues=['physical_copy_overflow:M1'])])
        self.assertEqual(result['structural_blocker_windows'], {'display_policy': 1, 'state_conflict': 1})
        self.assertEqual(summarize_windows([])['structural_blocker_windows'], {})

    def test_plain_summary_distinguishes_missing_old_stats_from_no_blockers(self):
        self.assertIn('未统计', format_advice_blockers(None))
        self.assertIn('无', format_advice_blockers({}))
        text = format_advice_blockers({'geometry': 10, 'hand_boundary': 2})
        self.assertIn('10窗', text)
        self.assertIn('局号', text)
        self.assertNotIn('河牌', text)

