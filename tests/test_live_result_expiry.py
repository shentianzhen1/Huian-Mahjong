"""Fresh capture must survive an expired advisory without exposing old hints."""
from collections import deque
from pathlib import Path
import queue
from types import SimpleNamespace
from unittest import TestCase, skipIf
from unittest.mock import Mock, patch

from tests.test_live_opening_tracker import runtime_report
from workspace.hint_alpha.live_guard import LiveAdviceGuard
from workspace.hint_alpha.live_snapshot_stability import LiveSnapshotStability
from workspace.hint_alpha.runtime_pipeline import RuntimeAdvicePipeline

try:
    from workspace.hint_alpha.live_app import LiveHintAlphaApp
    from workspace.vision.tiles_v0_1.public_state import PublicStateObservation
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
        app.public_view = None
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
        report = runtime_report(frames=(3, 4, 5))
        report['runtime_elapsed_seconds'] = 1.8
        self.app.runtime_result_queue.put(('ok', 'runtime-live', 0, 10., report))
        self.tick(12.1)
        self.app._update_snapshot_view.assert_not_called()
        self.assertIn('BLOCKED', self.app.hint_status.set.call_args.args[0])
        event, payload = self.app.evidence.mark.call_args.args
        self.assertEqual(event, 'RUNTIME_RESULT_TOO_OLD')
        self.assertAlmostEqual(payload['capture_age_seconds'], 2.1)
        self.assertEqual(payload['runtime_elapsed_seconds'], 1.8)
        self.assertEqual(payload['freshness_limit_seconds'], 2.)
        self.assertEqual(self.app.evidence.mark.call_args.kwargs['source'],
                         {'sequence': 5, 'monotonic': 10.})

    def test_pending_hand_boundary_remains_blocked_after_result_expiry(self):
        self.app.runtime_advice_pipeline.hand_boundary_pending = True
        self.tick(12.1)
        self.read(9, 12.3)
        self.read(12, 12.5)
        event = self.app.evidence.mark.call_args.args[1]
        self.assertFalse(event['display_allowed'])
        self.assertIn('live_hand_boundary_unconfirmed', event['issues'])

    def show_public_reading(self):
        app = self.app
        del app._consume_public_result
        app.live_guard.last_result = None
        app.public_previous = None
        app.timeline_hand = 2
        app.timeline_scores = (1000, 1000)
        app.ui_gold_tile = 'S8'
        app.match_header_status = Mock()
        app.score_header_status = Mock()
        app.vision_status = Mock()
        self.queue_public_reading(captured=7.5, remaining=81)
        self.tick(12.)
        self.assertEqual(app.ui_remaining_tiles, 81)

    def queue_public_reading(self, *, captured, remaining):
        observation = PublicStateObservation(1000, 1000, 2, remaining, 2, 2, 2)
        self.app.public_result_queue.put((
            'ok', SimpleNamespace(observation=observation),
            {'sequence': 7, 'monotonic': captured}, .1,
        ))

    def test_public_reading_expires_once_while_ocr_remains_busy_then_recovers(self):
        self.show_public_reading()
        app = self.app
        public_queue = app.public_result_queue
        app.public_busy = True
        self.tick(12.5)
        self.assertEqual(app.ui_remaining_tiles, 81)

        self.tick(12.6)
        self.assertIsNone(app.ui_hand_number)
        self.assertIsNone(app.ui_score_pair)
        self.assertIsNone(app.ui_remaining_tiles)
        self.assertTrue(app.runtime_advice_pipeline.hand_boundary_pending)
        self.assertIs(app.public_result_queue, public_queue)
        self.assertTrue(app.public_busy)
        self.assertEqual(app.public_previous.remaining_tiles, 81)
        self.assertEqual(app.evidence.mark.call_args.args[0], 'PUBLIC_STATE_EXPIRED')
        self.assertEqual(app.evidence.mark.call_args.kwargs['source']['monotonic'], 7.5)
        marks = app.evidence.mark.call_count
        self.tick(12.7)
        self.assertEqual(app.evidence.mark.call_count, marks)

        self.queue_public_reading(captured=12., remaining=80)
        self.tick(12.8)
        self.assertEqual(app.ui_remaining_tiles, 80)
        self.assertFalse(app.runtime_advice_pipeline.hand_boundary_pending)
        self.read(9, 12.9)
        self.read(12, 13.1)
        self.assertTrue(app.evidence.mark.call_args.args[1]['display_allowed'])
        self.assertEqual(app.evidence.mark.call_args.args[1]['gold_tile'], 'S8')

    def test_queued_fresh_public_reading_supersedes_old_reading_before_expiry(self):
        self.show_public_reading()
        self.queue_public_reading(captured=12., remaining=80)
        self.tick(12.6)
        self.assertEqual(self.app.ui_remaining_tiles, 80)
        self.assertFalse(self.app.runtime_advice_pipeline.hand_boundary_pending)
        self.assertEqual([call.args[0] for call in self.app.evidence.mark.call_args_list],
                         ['PUBLIC_STATE', 'PUBLIC_STATE'])

    def test_feedback_saves_visible_ocr_with_its_own_source_and_age(self):
        self.show_public_reading()
        app = self.app
        partial = PublicStateObservation(None, None, 2, 80, 0, 2, 2)
        ocr_source = {'sequence': 7, 'monotonic': 12.}
        app.public_result_queue.put(('ok', SimpleNamespace(observation=partial),
                                     ocr_source, .1))
        self.tick(12.2)
        self.assertEqual(app.public_previous.score_pair, (1000, 1000))

        app.frame = object()
        app.source = {'sequence': 9, 'monotonic': 12.2}
        app.evidence.path = Path('session')
        app.evidence.save_frame.return_value = app.evidence.path / 'frames' / 'feedback.png'
        app.evidence_status = Mock()
        self.now.return_value = 13.
        app.mark_feedback('RECOGNITION_ERROR')
        saved = app.evidence.save_frame.call_args.kwargs
        self.assertEqual(saved['source'], app.source)
        self.assertEqual(saved['payload']['public_state_source'], ocr_source)
        self.assertEqual(saved['payload']['public_state_age_seconds'], 1.)
        self.assertIsNone(saved['payload']['public_state']['top_right_score'])
        self.assertEqual(saved['payload']['public_state']['remaining_tiles'], 80)

        self.now.return_value = 17.1
        app.mark_feedback('RECOGNITION_ERROR')
        stale = app.evidence.save_frame.call_args.kwargs['payload']
        self.assertIsNone(stale['public_state'])
        self.assertEqual(stale['public_state_source'], ocr_source)

