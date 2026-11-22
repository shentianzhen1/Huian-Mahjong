"""Exercise UI lifecycle methods without a display or Windows capture."""
from collections import deque
from types import SimpleNamespace
import queue
import unittest
from unittest.mock import Mock, patch

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

    def test_capture_reset_clears_visible_public_state_and_restarts_ocr(self):
        shell = self.shell()
        old_queue = shell.public_result_queue
        old_worker = shell.public_worker_thread = Mock()
        old_worker.is_alive.return_value = True
        shell.last_public_started = 10
        shell.public_disabled = False
        shell.ui_hand_number = 3
        shell.ui_remaining_tiles = 44
        shell.ui_score_pair = (1200, 800)
        shell.ui_gold_tile = "S8"
        shell.ui_hand_number_ok = True
        shell.table_hand_status = Mock()
        shell.table_meld_status = Mock()
        shell.match_header_status = Mock()
        shell._refresh_header = Mock()
        HintAlphaApp._invalidate_advice(shell, "capture reset")

        old_queue.put(("ok", object(), {"sequence": 100}, 0.1))
        HintAlphaApp._consume_public_result(shell)
        self.assertIsNone(shell.public_previous)
        for field in ("ui_hand_number", "ui_remaining_tiles", "ui_score_pair", "ui_gold_tile"):
            self.assertIsNone(getattr(shell, field))
        self.assertFalse(shell.ui_hand_number_ok)
        shell.table_hand_status.set.assert_called_once_with("我的手牌：UNKNOWN")
        shell.table_meld_status.set.assert_called_once_with("我的副露：UNKNOWN")
        shell._refresh_header.assert_called_once()

        shell.public_frames.extend([Mock(), Mock(), Mock()])
        shell.source = {"sequence": 3, "monotonic": 10.2}
        shell._public_worker = Mock()
        with patch("workspace.hint_alpha.app.threading.Thread") as thread:
            HintAlphaApp._schedule_public_read(shell, 10.2)
            thread.assert_not_called()
            self.assertFalse(shell.public_busy)
            self.assertIs(shell.public_worker_thread, old_worker)

            old_worker.is_alive.return_value = False
            shell.source = {"sequence": 4, "monotonic": 10.3}
            HintAlphaApp._schedule_public_read(shell, 10.3)
        self.assertTrue(shell.public_busy)
        thread.return_value.start.assert_called_once()
        self.assertIs(shell.public_worker_thread, thread.return_value)
        _, previous, source, result_queue = thread.call_args.kwargs["args"]
        self.assertIsNone(previous)
        self.assertEqual(source, {"sequence": 4, "monotonic": 10.3})
        self.assertIs(result_queue, shell.public_result_queue)
        self.assertIsNot(result_queue, old_queue)

    def test_capture_reset_waits_for_old_runtime_worker_before_restarting(self):
        shell = self.shell()
        shell.demo = False
        shell.evidence = SimpleNamespace(session_id="session")
        shell._runtime_worker = Mock()
        shell.last_runtime_started = 10.
        old_worker = shell.runtime_worker_thread = Mock()
        old_worker.is_alive.return_value = True
        old_queue = shell.runtime_result_queue
        HintAlphaApp._invalidate_advice(shell, "capture reset")

        for sequence, captured in ((4, 10.1), (5, 10.2), (6, 10.3)):
            shell.live_guard.observe(sequence, captured)
            shell.runtime_frames.append((sequence, captured, Mock()))
        with patch("workspace.hint_alpha.app.threading.Thread") as thread:
            HintAlphaApp._schedule_runtime_read(shell, 10.3)
            thread.assert_not_called()
            self.assertIs(shell.runtime_worker_thread, old_worker)
            self.assertFalse(shell.runtime_busy)

            old_worker.is_alive.return_value = False
            HintAlphaApp._schedule_runtime_read(shell, 10.3)
        thread.return_value.start.assert_called_once()
        self.assertTrue(shell.runtime_busy)
        self.assertIs(shell.runtime_worker_thread, thread.return_value)
        samples, session, generation, captured, result_queue = thread.call_args.kwargs["args"]
        self.assertEqual([sample[0] for sample in samples], [4, 5, 6])
        self.assertEqual((session, generation, captured), ("session", 1, 10.3))
        self.assertIs(result_queue, shell.runtime_result_queue)
        self.assertIsNot(result_queue, old_queue)

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
