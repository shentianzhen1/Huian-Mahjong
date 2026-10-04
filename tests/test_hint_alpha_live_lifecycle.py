"""Exercise UI lifecycle methods without a display or Windows capture."""
from collections import deque
from types import SimpleNamespace
import queue
import unittest
from unittest.mock import Mock

from workspace.hint_alpha.live_guard import LiveAdviceGuard

try:
    from workspace.hint_alpha.app import HintAlphaApp
except ImportError:
    HintAlphaApp = None


@unittest.skipIf(HintAlphaApp is None, 'optional UI/Vision dependencies unavailable')
class LiveLifecycleTests(unittest.TestCase):
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
