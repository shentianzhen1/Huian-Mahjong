"""Fresh capture must survive an expired advisory without exposing old hints."""
from collections import deque
import queue
from unittest import TestCase, skipIf
from unittest.mock import Mock, patch

from tests.test_live_opening_tracker import runtime_report
from workspace.hint_alpha.live_guard import LiveAdviceGuard
from workspace.hint_alpha.live_snapshot_stability import LiveSnapshotStability
from workspace.hint_alpha.runtime_pipeline import RuntimeAdvicePipeline

try:
    from workspace.hint_alpha.live_app import LiveHintAlphaApp
except ImportError:
    LiveHintAlphaApp = None


@skipIf(LiveHintAlphaApp is None, 'optional UI/Vision dependencies unavailable')
class LiveResultExpiryTests(TestCase):
    def setUp(self):
        self.app = app = LiveHintAlphaApp.__new__(LiveHintAlphaApp)
        app.runtime_advice_pipeline = RuntimeAdvicePipeline(stability_tracker=LiveSnapshotStability())
        app._gold_hand_number = 2
        app.live_guard = LiveAdviceGuard(active=True, last_frame=12., last_sequence=7,
                                        last_result=10.)
        app.runtime_frames = deque([(7, 12., object())])
        app.public_frames = deque([object()])
        app.runtime_result_queue = queue.Queue()
        app.public_result_queue = queue.Queue()
        app.public_previous = object()
        app.runtime_busy = app.public_busy = True
        app.evidence = Mock(session_id='runtime-live')
        app.source = {}
        app.last_runtime_event_key = ('old hint',)
        app.experimental_runtime_advisory = True
        app.demo = False
        app.session = None
        app.after = Mock()
        app._consume_public_result = Mock()
        app._consume_video_test_events = Mock()
        app._update_snapshot_view = Mock()
        app._refresh_health = Mock()
        for name in ('hint_status', 'hint_latency', 'runtime_status', 'turn_status',
                     'blocked_detail', 'table_hand_status', 'table_meld_status', 'capture_status'):
            setattr(app, name, Mock())
        for end, captured in ((3, 9.), (6, 10.)):
            result = app.runtime_advice_pipeline.evaluate(
                runtime_report(gold='S8', frames=(end-2, end-1, end)),
                captured=captured, experimental=True)
        self.assertTrue(result.display_allowed)
        self.clock = patch('time.monotonic', return_value=12.1)
        self.now = self.clock.start()
        self.addCleanup(self.clock.stop)

    def tick(self, now):
        self.now.return_value = now
        self.app.tick()

    def read(self, end, captured):
        self.app.live_guard.observe(end, captured)
        report = runtime_report(include_gold=False, frames=(end-2, end-1, end))
        self.app.runtime_result_queue.put(('ok', 'runtime-live', 0, captured, report))
        self.tick(captured + .1)

    def test_expiry_hides_hint_once_but_keeps_capture_gold_and_worker_queues(self):
        runtime_queue = self.app.runtime_result_queue
        public_queue = self.app.public_result_queue
        self.tick(12.1)
        self.assertEqual(self.app._gold_hand_number, 2)
        self.assertTrue(self.app.live_guard.active)
        self.assertEqual(self.app.live_guard.generation, 0)
        self.assertIs(self.app.runtime_result_queue, runtime_queue)
        self.assertIs(self.app.public_result_queue, public_queue)
        self.assertTrue(self.app.runtime_frames)
        self.assertTrue(self.app.public_frames)
        self.assertTrue(self.app.runtime_busy)
        self.assertIn('BLOCKED', self.app.hint_status.set.call_args.args[0])
        self.assertIn('暂无', self.app.hint_latency.set.call_args.args[0])
        marks = self.app.evidence.mark.call_count
        self.tick(12.2)
        self.assertEqual(self.app.evidence.mark.call_count, marks)
        self.read(9, 12.3)
        event = self.app.evidence.mark.call_args.args[1]
        self.assertFalse(event['display_allowed'])
        self.assertIn('live_hand_meld_waiting_confirmation', event['issues'])
        self.read(12, 12.5)
        event = self.app.evidence.mark.call_args.args[1]
        self.assertTrue(event['display_allowed'])
        self.assertEqual(event['gold_tile'], 'S8')

    def test_actual_capture_gap_clears_gold_and_rejects_old_queue(self):
        self.app.runtime_advice_pipeline.select_manual_gold('M4',
            source_session='runtime-live', stream_epoch=0)
        old_queue = self.app.runtime_result_queue
        self.tick(14.1)
        self.assertIsNone(self.app._gold_hand_number)
        self.assertFalse(self.app.live_guard.active)
        self.assertEqual(self.app.live_guard.generation, 1)
        self.assertIsNone(self.app.runtime_advice_pipeline.manual_gold)
        self.assertIsNot(self.app.runtime_result_queue, old_queue)
        old_queue.put(('ok', 'runtime-live', 0, 12., runtime_report(gold='S8')))
        self.assertTrue(self.app.runtime_result_queue.empty())

    def test_manual_gold_survives_hint_expiry_but_needs_fresh_hand_confirmation(self):
        self.app.runtime_advice_pipeline.select_manual_gold('M4',
            source_session='runtime-live', stream_epoch=0)
        self.tick(12.1)
        self.assertEqual(self.app.runtime_advice_pipeline.manual_gold.tile_id, 'M4')
        self.read(9, 12.3)
        self.assertFalse(self.app.evidence.mark.call_args.args[1]['display_allowed'])
        self.read(12, 12.5)
        event = self.app.evidence.mark.call_args.args[1]
        self.assertTrue(event['display_allowed'])
        self.assertEqual(event['gold_tile'], 'M4')

    def test_stale_queued_result_cannot_restore_expired_hint(self):
        self.app.runtime_result_queue.put(('ok', 'runtime-live', 0, 10., runtime_report()))
        self.tick(12.1)
        self.app._update_snapshot_view.assert_not_called()
        self.assertIn('BLOCKED', self.app.hint_status.set.call_args.args[0])

    def test_pending_hand_boundary_remains_blocked_after_result_expiry(self):
        self.app.runtime_advice_pipeline.hand_boundary_pending = True
        self.tick(12.1)
        self.read(9, 12.3)
        self.read(12, 12.5)
        event = self.app.evidence.mark.call_args.args[1]
        self.assertFalse(event['display_allowed'])
        self.assertIn('live_hand_boundary_unconfirmed', event['issues'])

