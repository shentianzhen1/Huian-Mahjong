"""Switching reference policy must not consume an older in-flight read."""
import ast
from collections import deque
from pathlib import Path
import queue
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from workspace.hint_alpha.live_guard import LiveAdviceGuard


class TrialReferenceSwitchFenceTests(unittest.TestCase):
    def setUp(self):
        source = ast.parse(Path('workspace/hint_alpha/app.py').read_text())
        app_class = next(n for n in source.body if isinstance(n, ast.ClassDef)
                         and n.name == 'HintAlphaApp')
        methods = [n for n in app_class.body if isinstance(n, ast.FunctionDef)
                   and n.name in ('_toggle_hand_source_trial', '_consume_runtime_result',
                                  '_schedule_runtime_read')]
        self.evaluate = Mock(side_effect=RuntimeError('fresh result reached evaluation'))
        self.namespace = dict(queue=queue, time=SimpleNamespace(monotonic=lambda: 20.),
                              evaluate_runtime_report=self.evaluate,
                              threading=Mock(),
                              __name__='workspace.hint_alpha.app',
                              __package__='workspace.hint_alpha')
        exec(compile(ast.Module(body=methods, type_ignores=[]), '<actual-switch>', 'exec'),
             self.namespace)
        self.manual_gold = object()
        pipeline = SimpleNamespace(allow_unvalidated_hand_sources=False,
            opening_tracker=Mock(), stability_tracker=Mock(), manual_gold=self.manual_gold)
        self.app = SimpleNamespace(runtime_advice_pipeline=pipeline,
            runtime_frames=deque([(1, 19.5, object()), (2, 19.7, object())]),
            single_source_hand_trial=Mock(get=Mock(return_value=True)),
            evidence=SimpleNamespace(session_id='s', mark=Mock()), hint_status=Mock(),
            blocked_detail=Mock(), hint_latency=Mock(),
            experimental_runtime_advisory=False,
            runtime_busy=True, runtime_result_queue=queue.Queue(),
            live_guard=LiveAdviceGuard(active=True, generation=4))

    def toggle(self):
        self.namespace['_toggle_hand_source_trial'](self.app)

    def consume(self):
        self.namespace['_consume_runtime_result'](self.app)

    def test_switch_clears_old_frames_and_preserves_manual_gold_and_epoch(self):
        self.toggle()
        self.assertEqual(len(self.app.runtime_frames), 0)
        self.assertEqual(self.app.runtime_observation_not_before, 20.)
        self.assertIs(self.app.runtime_advice_pipeline.manual_gold, self.manual_gold)
        self.assertEqual(self.app.live_guard.generation, 4)
        self.app.runtime_advice_pipeline.stability_tracker.reset.assert_called_once()

    def test_old_success_and_error_cannot_replace_waiting_state(self):
        self.toggle()
        for kind, value in [('ok', {}), ('error', 'old failure')]:
            with self.subTest(kind=kind):
                self.app.runtime_busy = True
                calls = self.app.hint_status.set.call_count
                self.app.runtime_result_queue.put((kind, 's', 4, 19.9, value))
                self.consume()
                self.assertFalse(self.app.runtime_busy)
                self.assertIsNone(self.app.live_guard.last_result)
                self.assertEqual(self.app.hint_status.set.call_count, calls)
                self.evaluate.assert_not_called()

    def test_fresh_result_after_switch_can_reach_evaluation(self):
        self.toggle()
        self.app.runtime_result_queue.put(('ok', 's', 4, 20., {}))
        self.consume()  # Boundary itself is not a fresh post-switch frame.
        self.evaluate.assert_not_called()
        self.namespace['time'].monotonic = lambda: 20.2
        self.app.runtime_result_queue.put(('ok', 's', 4, 20.1, {}))
        with self.assertRaisesRegex(RuntimeError, 'fresh result reached evaluation'):
            self.consume()
        self.assertEqual(self.app.live_guard.last_result, 20.1)
        self.evaluate.assert_called_once()

    def test_pending_old_capture_cannot_prime_a_new_burst(self):
        self.toggle()
        self.app.demo = False
        self.app.runtime_busy = False
        self.app.last_runtime_started = 0.
        self.app._runtime_worker = Mock()
        self.app.live_guard.last_frame = 20.2
        self.app.runtime_frames.extend((n, captured, Mock())
            for n, captured in [(1, 19.9), (2, 20.1), (3, 20.2)])
        self.namespace['_schedule_runtime_read'](self.app, 20.2)
        self.namespace['threading'].Thread.assert_not_called()
        self.assertFalse(self.app.runtime_busy)
        self.app.runtime_frames[0] = (1, 20.05, Mock())
        self.namespace['_schedule_runtime_read'](self.app, 20.2)
        self.namespace['threading'].Thread.assert_called_once()
        self.assertTrue(self.app.runtime_busy)
