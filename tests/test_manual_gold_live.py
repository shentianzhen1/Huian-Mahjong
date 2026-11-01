"""User-selected Gold must unblock only Gold, inside the current capture/hand."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tests.test_live_opening_tracker import runtime_report
from workspace.hint_alpha.runtime_pipeline import RuntimeAdvicePipeline, evaluate_runtime_report
from workspace.hint_alpha.live_snapshot_stability import LiveSnapshotStability


class ManualGoldLiveTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = RuntimeAdvicePipeline()
        self.pipeline.select_manual_gold('M4', source_session='runtime-live', stream_epoch=0)

    def evaluate(self, report=None):
        return self.pipeline.evaluate(report or runtime_report(include_gold=False), captured=1., experimental=True)

    def test_missing_or_conflicting_visual_gold_uses_explicit_user_input(self):
        for report in (runtime_report(include_gold=False), runtime_report(gold='B')):
            result = self.evaluate(report)
            self.assertTrue(result.display_allowed)
            self.assertEqual(result.snapshot.gold_tile, 'M4')
            self.assertEqual(result.opening_fact.source_kind, 'MANUAL_USER_SELECTED')
            self.assertFalse(result.safe_for_executor)
            self.assertFalse(result.opening_fact.safe_for_environment_state)
            self.assertFalse(result.opening_fact.selection_inference_used)
            self.assertFalse(any(i.startswith('runtime_gold_') for i in result.hint.issues))

    def test_unknown_hand_and_geometry_still_block(self):
        for geometry in (False, True):
            report = runtime_report(include_gold=False)
            if geometry:
                report['geometry_untrusted'] = True
            else:
                report['components'][0]['tile_id'] = 'UNKNOWN'
                report['all_concealed_tile_ids_trusted'] = False
            result = self.evaluate(report)
            self.assertFalse(result.display_allowed)
            self.assertTrue(result.snapshot.gold_trusted)

    def test_scope_changes_do_not_inherit_manual_gold(self):
        for changes in (dict(session='other'), dict(epoch=1)):
            result = self.evaluate(runtime_report(include_gold=False, **changes))
            self.assertIsNone(result.snapshot.gold_tile)
            self.assertFalse(result.display_allowed)

    def test_clear_does_not_leave_manual_gold_in_visual_memory(self):
        self.assertTrue(self.evaluate().display_allowed)
        self.pipeline.reset()
        self.assertIsNone(self.pipeline.manual_gold)
        self.assertIsNone(self.evaluate().snapshot.gold_tile)

    def test_bound_ui_path_and_confirmation_restart_on_edit(self):
        self.pipeline.stability_tracker = LiveSnapshotStability()
        with self.pipeline.bind():
            result = evaluate_runtime_report(runtime_report(include_gold=False), captured=1., experimental=True)
        self.assertEqual(result.opening_fact.source_kind, 'MANUAL_USER_SELECTED')
        self.assertFalse(result.display_allowed)
        result = self.pipeline.evaluate(runtime_report(include_gold=False, frames=(4,5,6)), captured=1.8, experimental=True)
        self.assertTrue(result.display_allowed)
        self.pipeline.select_manual_gold('P9', source_session='runtime-live', stream_epoch=0)
        result = self.pipeline.evaluate(runtime_report(include_gold=False, frames=(7,8,9)), captured=2.6, experimental=True)
        self.assertEqual(result.snapshot.gold_tile, 'P9')
        self.assertFalse(result.display_allowed)

    def test_flower_unknown_and_empty_scope_are_rejected(self):
        for tile in ('UNKNOWN', 'F1', None):
            with self.assertRaises(ValueError):
                self.pipeline.select_manual_gold(tile, source_session='runtime-live', stream_epoch=0)
        with self.assertRaises(ValueError):
            self.pipeline.select_manual_gold('M4', source_session='', stream_epoch=0)


try:
    from workspace.hint_alpha.live_app import LiveHintAlphaApp
    from workspace.hint_alpha.app import HintAlphaApp
except ImportError:
    LiveHintAlphaApp = None


@unittest.skipIf(LiveHintAlphaApp is None, 'UI dependencies unavailable')
class ManualGoldHandBoundaryTests(unittest.TestCase):
    def test_ui_selection_and_clear_update_pipeline_and_provenance(self):
        app = LiveHintAlphaApp.__new__(LiveHintAlphaApp)
        app.runtime_advice_pipeline = RuntimeAdvicePipeline()
        app.evidence = Mock(session_id='runtime-live')
        app.session = object()
        app.live_guard = SimpleNamespace(generation=2, active=True)
        app.manual_gold_status = Mock()
        app.hint_status = Mock()
        with patch.object(HintAlphaApp, '_refresh_health'):
            app._select_manual_gold('M4')
            self.assertEqual(app.runtime_advice_pipeline.manual_gold.tile_id, 'M4')
            self.assertEqual(app.runtime_advice_pipeline.manual_gold.stream_epoch, 2)
            self.assertIn('手动', app.manual_gold_status.set.call_args.args[0])
            self.assertEqual(app.evidence.mark.call_args.args[0], 'MANUAL_GOLD_SELECTED')
            app.clear_manual_gold()
            self.assertIsNone(app.runtime_advice_pipeline.manual_gold)
            self.assertFalse(app.ui_gold_ok)
            self.assertIsNone(app.ui_gold_tile)

    def test_initial_hand_keeps_selection_next_hand_and_capture_stop_clear_it(self):
        app = LiveHintAlphaApp.__new__(LiveHintAlphaApp)
        app.runtime_advice_pipeline = RuntimeAdvicePipeline()
        app.runtime_advice_pipeline.select_manual_gold('M4', source_session='runtime-live', stream_epoch=0)
        app._gold_hand_number = None
        with patch.object(HintAlphaApp, '_update_public_view'):
            app._update_public_view(SimpleNamespace(hand_number=3, hand_votes=2))
            self.assertEqual(app.runtime_advice_pipeline.manual_gold.tile_id, 'M4')
            app._update_public_view(SimpleNamespace(hand_number=4, hand_votes=2))
            self.assertIsNone(app.runtime_advice_pipeline.manual_gold)
        app.runtime_advice_pipeline.select_manual_gold('S9', source_session='runtime-live', stream_epoch=0)
        with patch.object(HintAlphaApp, '_invalidate_advice'):
            app._invalidate_advice('stopped')
        self.assertIsNone(app.runtime_advice_pipeline.manual_gold)
