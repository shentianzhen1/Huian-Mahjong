from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tests.test_live_opening_tracker import runtime_report
from workspace.hint_alpha.hand_source_trial import trial_hand_report
from workspace.hint_alpha.runtime_pipeline import RuntimeAdvicePipeline
from workspace.hint_alpha.live_snapshot_stability import LiveSnapshotStability
from workspace.vision.current_state_snapshot import assess_current_snapshot, SnapshotCapability


def source_rejected_report(frame=3):
    report = runtime_report(include_gold=False, frames=(frame-2, frame-1, frame))
    for item in report['components']:
        if item['tile_id'] == 'P2':
            item.update(candidate_tile_id='P2',tile_id='UNKNOWN',tile_confidence=.9,
                        identity_reason='class_not_cross_session_validated_in_region')
    report['all_concealed_tile_ids_trusted'] = False
    return report


class HandSourceTrialTests(unittest.TestCase):
    def pipeline(self, enabled=True, stable=False):
        p = RuntimeAdvicePipeline(allow_unvalidated_hand_sources=enabled,
                                  stability_tracker=LiveSnapshotStability() if stable else None)
        p.select_manual_gold('B', source_session='runtime-live', stream_epoch=0)
        return p

    def test_raw_rejections_remain_unchanged_and_default_stays_blocked(self):
        report = source_rejected_report()
        original = deepcopy(report)
        copied, used = trial_hand_report(report)
        self.assertEqual(report, original)
        self.assertEqual(used, ('P2',))
        selected = next(c for c in copied['components'] if c.get('candidate_tile_id') == 'P2')
        self.assertEqual(selected['original_identity_reason'], 'class_not_cross_session_validated_in_region')
        self.assertFalse(self.pipeline(False).evaluate(report,captured=1,experimental=True).display_allowed)
        self.assertFalse(self.pipeline().evaluate(report,captured=1,experimental=False).display_allowed)

    def test_trial_needs_confirmation_and_only_allows_structural_advice(self):
        p = self.pipeline(stable=True)
        first = p.evaluate(source_rejected_report(),captured=1,experimental=True)
        self.assertFalse(first.display_allowed)
        second = p.evaluate(source_rejected_report(6),captured=1.8,experimental=True)
        self.assertTrue(second.display_allowed)
        self.assertTrue(second.hand_source_trial)
        self.assertFalse(second.safe_for_executor)
        assessment = assess_current_snapshot(second.snapshot)
        self.assertFalse(assessment.allows(SnapshotCapability.VISIBLE_REMAINDERS))
        self.assertFalse(assessment.allows(SnapshotCapability.DANGER_HINT))
        self.assertIn('experimental_hand_sources_unvalidated', second.hint.issues)

    def test_low_nonfinite_missing_class_and_other_roles_never_bypass(self):
        for score,reason,region,candidate in [
            (.819,'class_not_cross_session_validated_in_region','hand','P2'),
            (float('nan'),'class_not_cross_session_validated_in_region','hand','P2'),
            (True,'class_not_cross_session_validated_in_region','hand','P2'),
            (.99,'category_has_missing_standard_class','hand','P2'),
            (.99,'class_missing_real_gold_skin_example','hand','P2'),
            (.99,'class_not_cross_session_validated_in_region','gold','P2'),
            (.99,'class_not_cross_session_validated_in_region','meld','P2'),
            (.99,'class_not_cross_session_validated_in_region','hand','UNKNOWN')]:
            with self.subTest(score=score,reason=reason,region=region,candidate=candidate):
                report = dict(components=[dict(tile_id='UNKNOWN',candidate_tile_id=candidate,
                    tile_confidence=score,identity_reason=reason,region_candidate=region)])
                _, used = trial_hand_report(report)
                self.assertFalse(used)

    def test_geometry_count_and_physical_conflict_still_block(self):
        for defect in ('geometry','count','physical'):
            report = source_rejected_report()
            if defect == 'geometry':report['geometry_untrusted'] = True
            elif defect == 'count':report['concealed_tile_count'] += 1
            else:
                for item in report['components'][:5]:
                    item.update(tile_id='P9',identity_reason='accepted',tile_confidence=.95)
            self.assertFalse(self.pipeline().evaluate(report,captured=1,experimental=True).display_allowed)

    def test_bound_ui_path_records_trial(self):
        p = self.pipeline()
        from workspace.hint_alpha.runtime_pipeline import evaluate_runtime_report
        with p.bind():
            result = evaluate_runtime_report(source_rejected_report(),captured=1,experimental=True)
        self.assertTrue(result.hand_source_trial)
        self.assertTrue(result.display_allowed)


try:
    from workspace.hint_alpha.app import HintAlphaApp
    from workspace.hint_alpha.live_app import LiveHintAlphaApp
except ImportError:
    LiveHintAlphaApp = None


@unittest.skipIf(LiveHintAlphaApp is None,'UI unavailable')
class HandSourceTrialUITests(unittest.TestCase):
    def test_toggle_restarts_confirmation_without_clearing_manual_gold(self):
        app = LiveHintAlphaApp.__new__(LiveHintAlphaApp)
        app.runtime_advice_pipeline = RuntimeAdvicePipeline(stability_tracker=LiveSnapshotStability())
        app.runtime_advice_pipeline.select_manual_gold('M4',source_session='runtime-live',stream_epoch=0)
        app.single_source_hand_trial = Mock(get=Mock(return_value=True))
        app.evidence = Mock()
        app.hint_status = Mock()
        app.blocked_detail = Mock()
        app.hint_latency = Mock()
        app._toggle_hand_source_trial()
        self.assertTrue(app.runtime_advice_pipeline.allow_unvalidated_hand_sources)
        self.assertEqual(app.runtime_advice_pipeline.manual_gold.tile_id,'M4')
        self.assertEqual(app.evidence.mark.call_args.args[0],'HAND_SOURCE_TRIAL_MODE')
