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
