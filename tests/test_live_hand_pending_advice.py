"""Exercise the actual live UI consumer across an unresolved hand boundary."""
from collections import deque
import queue
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tests.test_live_opening_tracker import runtime_report
from workspace.hint_alpha.live_guard import LiveAdviceGuard
from workspace.hint_alpha.runtime_pipeline import RuntimeAdvicePipeline

try:
    from workspace.hint_alpha.app import HintAlphaApp
    from workspace.hint_alpha.live_app import LiveHintAlphaApp
except ImportError:
    LiveHintAlphaApp = None


@unittest.skipIf(LiveHintAlphaApp is None, 'optional UI/Vision dependencies unavailable')
class LiveHandPendingAdviceTests(unittest.TestCase):
    def setUp(self):
        self.app = LiveHintAlphaApp.__new__(LiveHintAlphaApp)
        app = self.app
        app.runtime_advice_pipeline = RuntimeAdvicePipeline()
        app._gold_hand_number = None
        app.runtime_frames = deque()
        app.runtime_result_queue = queue.Queue()
        app.live_guard = LiveAdviceGuard(active=True, generation=0)
        app.evidence = Mock(session_id='runtime-live')
        app.last_runtime_event_key = None
        app.source = None
        app.experimental_runtime_advisory = True
        for name in ('hint_status', 'hint_latency', 'runtime_status', 'turn_status',
                     'blocked_detail', 'table_hand_status', 'table_meld_status'):
            setattr(app, name, Mock())
        app._update_snapshot_view = Mock()
        app._refresh_health = Mock()
        self.clock = patch('time.monotonic', return_value=100.)
        self.now = self.clock.start()
        self.addCleanup(self.clock.stop)
        self.public_display = patch.object(HintAlphaApp, '_update_public_view')
        self.public_display.start()
        self.addCleanup(self.public_display.stop)
        self.observe(2)
        app.runtime_advice_pipeline.evaluate(runtime_report(gold='S8'),
                                             captured=100.1, experimental=True)

    def observe(self, hand, votes=2):
        self.app._update_public_view(SimpleNamespace(hand_number=hand, hand_votes=votes))

    def consume(self, captured, *, gold=None):
        self.now.return_value = captured + .05
        report = runtime_report(gold=gold or 'S8', include_gold=gold is not None,
                                frames=(4, 5, 6))
        self.app.runtime_result_queue.put(('ok', 'runtime-live', 0, captured, report))
        self.app._consume_runtime_result()

    def test_missing_low_vote_jump_and_regression_hide_old_gold_advice(self):
        for hand, votes in ((None, 1), (2, 1), (5, 2), (1, 2)):
            with self.subTest(hand=hand, votes=votes):
                self.now.return_value = 101.
                self.observe(hand, votes)
                # Previously displayed advice is hidden without waiting for a worker.
                self.assertIn('BLOCKED', self.app.hint_status.set.call_args.args[0])
                self.consume(101.1)
                event = self.app.evidence.mark.call_args.args[1]
                self.assertFalse(event['display_allowed'])
                self.assertIsNone(event['shanten'])
                self.assertEqual(event['best_discards'], [])
                self.assertIsNone(event['gold_tile'])
                self.assertIn('live_hand_boundary_unconfirmed', event['issues'])

    def test_same_hand_recovery_preserves_gold_but_rejects_preconfirmation_result(self):
        self.now.return_value = 101.
        self.observe(None, 1)
        self.now.return_value = 102.
        self.observe(2)
        self.app._update_snapshot_view.reset_mock()
        self.consume(101.9)
        self.app._update_snapshot_view.assert_not_called()
        self.consume(102.1)
        event = self.app.evidence.mark.call_args.args[1]
        self.assertTrue(event['display_allowed'])
        self.assertEqual(event['gold_tile'], 'S8')

    def test_next_hand_clears_gold_and_preboundary_buffer(self):
        self.app.runtime_frames.append((1, 100.1, object()))
        self.now.return_value = 101.
        self.observe(3)
        self.assertFalse(self.app.runtime_frames)
        self.consume(100.9, gold='S8')
        self.app._update_snapshot_view.assert_not_called()
        self.consume(101.1)
        event = self.app.evidence.mark.call_args.args[1]
        self.assertFalse(event['display_allowed'])
        self.assertIsNone(event['gold_tile'])
        self.consume(101.3, gold='M4')
        self.assertTrue(self.app.evidence.mark.call_args.args[1]['display_allowed'])

    def test_manual_gold_does_not_override_pending_hand_boundary(self):
        self.now.return_value = 101.
        self.observe(None, 1)
        self.app.runtime_advice_pipeline.select_manual_gold('M4',
            source_session='runtime-live', stream_epoch=0)
        self.consume(101.1)
        event = self.app.evidence.mark.call_args.args[1]
        self.assertFalse(event['display_allowed'])
        self.assertIsNone(event['shanten'])

    def test_public_worker_error_also_pauses_advice(self):
        self.app.public_result_queue = queue.Queue()
        self.app.public_result_queue.put(('error', 'OCR failed'))
        self.app.vision_status = Mock()
        self.now.return_value = 101.
        self.app._consume_public_result()
        self.consume(101.1)
        self.assertFalse(self.app.evidence.mark.call_args.args[1]['display_allowed'])

    def test_prior_identity_from_before_confirmation_cannot_prime_new_read(self):
        from copy import deepcopy
        from workspace.hint_alpha.live_snapshot_stability import LiveSnapshotStability
        self.app.runtime_advice_pipeline.stability_tracker = LiveSnapshotStability()
        self.now.return_value = 101.
        self.observe(3)
        report = runtime_report(gold='M4', frames=(4, 5, 6))
        prior = deepcopy(report)
        for component in prior['components']:
            component['frame'] = 5
        report.update(prior_identity_report=prior, prior_identity_captured=100.9)
        self.now.return_value = 101.2
        self.app.runtime_result_queue.put(('ok', 'runtime-live', 0, 101.1, report))
        self.app._consume_runtime_result()
        event = self.app.evidence.mark.call_args.args[1]
        self.assertFalse(event['display_allowed'])
        self.assertIn('live_hand_meld_waiting_confirmation', event['issues'])

    def test_pending_pipeline_binding_is_scoped_and_does_not_poison_gold(self):
        from workspace.hint_alpha.runtime_pipeline import evaluate_runtime_report
        self.observe(None, 1)
        pipeline = self.app.runtime_advice_pipeline
        report = runtime_report(gold='M4')
        with pipeline.bind():
            result = evaluate_runtime_report(report, captured=101.1, experimental=True)
            self.assertFalse(result.display_allowed)
        # An unrelated stateless caller is not blocked by the UI context.
        self.assertTrue(evaluate_runtime_report(report, captured=101.2,
                                              experimental=True).display_allowed)
        self.observe(2)
        result = pipeline.evaluate(runtime_report(include_gold=False),
                                   captured=102., experimental=True)
        self.assertTrue(result.display_allowed)
        self.assertEqual(result.snapshot.gold_tile, 'S8')

