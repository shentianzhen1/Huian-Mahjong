import ast
from pathlib import Path
from types import SimpleNamespace
import queue
import threading
import time
import unittest
from unittest.mock import Mock, patch

try:
    from workspace.vision.tiles_runtime_v0_2 import runtime_reader, dynamic_geometry
except ImportError:
    runtime_reader = None


@unittest.skipUnless(runtime_reader is not None, 'Vision dependencies unavailable')
class RuntimeParallelIdentityTests(unittest.TestCase):
    def test_trial_off_does_not_inject_bundled_reference_classifier(self):
        from workspace.vision.tiles_runtime_v0_2 import experimental_hand_translation, local_meld_trial
        source = ast.parse(Path('workspace/hint_alpha/app.py').read_text())
        app = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == 'HintAlphaApp')
        method = next(n for n in app.body if isinstance(n, ast.FunctionDef) and n.name == '_runtime_worker')
        namespace = {'time': time, 'queue': queue, 'PROJECT_ROOT': Path.cwd()}
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<worker>', 'exec'), namespace)
        for enabled in (False, True, False):
            with self.subTest(enabled=enabled):
                output = queue.Queue()
                seen = []
                def read(*args, **kwargs):
                    seen.append(kwargs.get('resources', {}).get('classifier', 'base'))
                    self.assertEqual(kwargs['confidence_threshold'], .82)
                    return {'geometry_untrusted': True}
                with patch.object(runtime_reader, 'read_stable_frames', side_effect=read), \
                     patch.object(runtime_reader, 'prepare_runtime_resources', return_value={'classifier': 'base'}), \
                     patch.object(experimental_hand_translation, 'cached_private_hand_packet',
                                  return_value={'classifier': 'trial'}) as loader, \
                     patch.object(local_meld_trial, 'with_local_meld_trial', side_effect=lambda x: x), \
                     patch.object(dynamic_geometry, 'detect_dynamic_geometry', return_value=object()):
                    namespace['_runtime_worker'](SimpleNamespace(experimental_hand_packet=Path('bundled.json'),
                        experimental_edge_seams=enabled), [(1, 1., Mock()), (2, 1.1, Mock())],
                        's', 4, 1.1, output)
                self.assertEqual(output.get_nowait()[0], 'ok')
                self.assertEqual(loader.call_count, int(enabled))
                self.assertEqual(seen, ['trial' if enabled else 'base'] * 2)

    def test_real_worker_joins_two_reads_with_original_frame_ids_and_timestamps(self):
        source=ast.parse(Path('workspace/hint_alpha/app.py').read_text())
        app=next(n for n in source.body if isinstance(n,ast.ClassDef) and n.name=='HintAlphaApp')
        method=next(n for n in app.body if isinstance(n,ast.FunctionDef) and n.name=='_runtime_worker')
        namespace={'time':time,'queue':queue,'PROJECT_ROOT':Path.cwd()}
        exec(compile(ast.Module(body=[method],type_ignores=[]),'<worker>', 'exec'),namespace)
        barrier=threading.Barrier(2,timeout=3)
        def read(images,root,*,frame_ids,identity_frame_id=None,**kwargs):
            self.assertEqual(frame_ids,(72,78,84))
            self.assertEqual(set(kwargs['geometry_cache']),{('s',72),('s',78),('s',84)})
            barrier.wait()
            return {'geometry_untrusted':False,'classified_frame':identity_frame_id or frame_ids[-1]}
        output=queue.Queue()
        with patch.object(runtime_reader,'read_stable_frames',side_effect=read), \
             patch.object(dynamic_geometry,'detect_dynamic_geometry',return_value=object()) as detector:
            namespace['_runtime_worker'](SimpleNamespace(),[(n,n/30,Mock()) for n in [72,78,84]],
                's',4,2.8,output)
        kind,session,epoch,captured,report=output.get_nowait()
        self.assertEqual((kind,session,epoch,captured),('ok','s',4,2.8))
        self.assertEqual(report['classified_frame'],84)
        self.assertEqual(report['prior_identity_report']['classified_frame'],78)
        self.assertEqual(report['prior_identity_captured'],2.6)
        self.assertEqual(report['prior_identity_report']['stream_epoch'],4)
        self.assertEqual(detector.call_count,3)
