"""Exercise UI lifecycle methods without a display or Windows capture."""
from collections import deque
from types import SimpleNamespace
import queue
import unittest
from unittest.mock import Mock

from workspace.hint_alpha.live_guard import LiveAdviceGuard
from workspace.hint_alpha.runtime_pipeline import evaluate_runtime_report

try:
    from workspace.hint_alpha.app import HintAlphaApp
except ImportError:
    HintAlphaApp = None


@unittest.skipIf(HintAlphaApp is None, 'optional UI/Vision dependencies unavailable')
class LiveLifecycleTests(unittest.TestCase):
    def test_unknown_reason_is_visible_but_promoted_gate_stays_closed(self):
        hand = ['M1', 'M2', 'M3', 'M4', 'M5', 'M6', 'M7', 'M8', 'M9',
                'P1', 'P2', 'P3', 'S1', 'S2', 'S3', 'E']
        report = dict(session='synthetic-ui', stream_epoch=0, frames=[1, 2, 3],
                      geometry_untrusted=False, concealed_tile_count=16,
                      all_concealed_tile_ids_trusted=True, safe_for_hint=False,
                      gold_identity_observations=[
                          dict(frame=frame, candidate_tile_id='B', tile_id='B',
                               tile_confidence=0.95, identity_reason='accepted')
                          for frame in (1, 2, 3)],
                      components=[dict(region_candidate='hand', tile_id=tile,
                                       identity_reason='accepted') for tile in hand]
                      + [dict(region_candidate='gold', tile_id='B',
                              identity_reason='accepted')])
        trusted_report = dict(report, components=[dict(item) for item in report['components']])
        report['components'][0]['tile_id'] = 'UNKNOWN'
        report['all_concealed_tile_ids_trusted'] = False
        blocked = evaluate_runtime_report(report, captured=1, experimental=True)
        text = HintAlphaApp._format_runtime_advice(
            blocked, experimental=True, promoted=False)
        self.assertIn('hand_untrusted', text)
        self.assertNotIn('promotion', text)
        trusted = evaluate_runtime_report(trusted_report, captured=2)
        self.assertIn('promotion', HintAlphaApp._format_runtime_advice(
            trusted, experimental=False, promoted=False))
        experimental = evaluate_runtime_report(trusted_report, captured=2,
                                               experimental=True)
        self.assertTrue(HintAlphaApp._format_runtime_advice(
            experimental, experimental=True, promoted=False).startswith('实验 '))

    def shell(self):
        return SimpleNamespace(
            live_guard=LiveAdviceGuard(), runtime_frames=deque([1, 2, 3]),
            public_frames=deque([1, 2, 3]), runtime_busy=True, public_busy=True,
            runtime_result_queue=queue.Queue(), public_result_queue=queue.Queue(),
            public_previous=object(), hint_status=Mock(), evidence=None,
        )

    def test_invalidation_discards_worker_queues_and_visible_advice(self):
        shell = self.shell()
        old_queue = shell.runtime_result_queue
        shell.live_guard.observe(1, 10)
        HintAlphaApp._invalidate_advice(shell, 'black frame')
        old_queue.put(('ok', 'old', 0, 10, {}))
        self.assertTrue(shell.runtime_result_queue.empty())
        self.assertFalse(shell.runtime_frames)
        self.assertFalse(shell.public_frames)
        self.assertIsNone(shell.public_previous)
        self.assertFalse(shell.runtime_busy)
        self.assertIn('BLOCKED', shell.hint_status.set.call_args.args[0])

    def test_queued_old_epoch_cannot_restore_hint(self):
        shell = self.shell()
        shell.evidence = SimpleNamespace(session_id='same-session')
        shell.live_guard.invalidate()
        shell.live_guard.observe(1, 10)
        shell.runtime_result_queue.put(('ok', 'same-session', 0, 10, {}))
        HintAlphaApp._consume_runtime_result(shell)
        shell.hint_status.set.assert_not_called()

    def test_stop_records_recorder_failure_and_closes_other_resources(self):
        shell = self.shell()
        shell._invalidate_advice = Mock()
        shell.auto_recorder = Mock()
        shell.auto_recorder.close.side_effect = OSError('disk full')
        capture = shell.session = Mock()
        evidence = shell.evidence = Mock()
        shell.canvas = Mock()
        shell.capture_status = Mock()
        shell.evidence_status = Mock()
        HintAlphaApp.stop(shell)
        capture.close.assert_called_once()
        evidence.mark.assert_called_once()
        self.assertEqual(evidence.mark.call_args.args[0], 'SHUTDOWN_FAILED')
        evidence.close.assert_called_once_with('capture_stopped_with_errors')
        self.assertIn('保存失败', shell.capture_status.set.call_args.args[0])

    def test_stop_preserves_evidence_handle_after_close_failure(self):
        shell = self.shell()
        shell._invalidate_advice = Mock()
        shell.auto_recorder = shell.session = None
        evidence = shell.evidence = Mock()
        evidence.close.side_effect = OSError('completion write failed')
        shell.canvas = Mock()
        shell.capture_status = Mock()
        shell.evidence_status = Mock()
        HintAlphaApp.stop(shell)
        self.assertIs(shell.evidence, evidence)
        self.assertIn('证据关闭失败', shell.evidence_status.set.call_args.args[0])

    def test_manual_session_stops_capture_and_does_not_claim_vision(self):
        shell = SimpleNamespace(manual_active=False, evidence=None,
                                stop=Mock(), _start_evidence=Mock(),
                                capture_status=Mock(), runtime_status=Mock(),
                                vision_status=Mock(), demo=True,
                                source={'old_capture': True})
        self.assertTrue(HintAlphaApp._start_manual_session(shell))
        shell.stop.assert_called_once()
        shell._start_evidence.assert_called_once()
        self.assertFalse(shell.demo)
        self.assertEqual(shell.backend_name, 'MANUAL')
        self.assertEqual(shell.source, {})
        self.assertEqual(shell.manual_revision, 0)
        self.assertTrue(shell.manual_active)
        self.assertIn('无画面采集', shell.capture_status.set.call_args.args[0])

    def test_manual_session_refuses_after_failed_evidence_close(self):
        shell = SimpleNamespace(manual_active=False, evidence=None, stop=Mock(),
                                _start_evidence=Mock())
        def fail_close():
            shell.evidence = object()
        shell.stop.side_effect = fail_close
        with unittest.mock.patch('workspace.hint_alpha.app.messagebox.showerror'):
            self.assertFalse(HintAlphaApp._start_manual_session(shell))
        shell._start_evidence.assert_not_called()
