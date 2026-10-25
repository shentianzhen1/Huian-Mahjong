"""Exercise the real scheduler without constructing Tk or starting threads."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import unittest


class RuntimeScheduleLatencyTests(unittest.TestCase):
    def test_latest_burst_schedules_at_point_four_without_overlap(self):
        tree = ast.parse(Path('workspace/hint_alpha/app.py').read_text())
        app = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'HintAlphaApp')
        method = next(n for n in app.body if isinstance(n, ast.FunctionDef) and n.name == '_schedule_runtime_read')
        thread = Mock()
        namespace = {'threading': SimpleNamespace(Thread=thread)}
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<scheduler>', 'exec'), namespace)
        schedule = namespace['_schedule_runtime_read']
        state = SimpleNamespace(demo=False, runtime_busy=False,
            runtime_frames=[(i, Mock()) for i in range(3)], last_runtime_started=0.,
            evidence=SimpleNamespace(session_id='session'), _runtime_worker=Mock(),
            live_guard=SimpleNamespace(generation=1, last_frame=.4), runtime_result_queue=Mock())
        schedule(state, .39)
        thread.assert_not_called()
        schedule(state, .4)
        thread.assert_called_once()
        thread.return_value.start.assert_called_once()
        self.assertEqual([i for i, _ in thread.call_args.kwargs['args'][0]], [0, 1, 2])
        schedule(state, 1.)
        thread.assert_called_once()  # still busy: do not accumulate jobs
        state.runtime_busy = False
        state.runtime_frames = state.runtime_frames[:2]
        schedule(state, 1.)
        thread.assert_called_once()  # keep the three-frame requirement
