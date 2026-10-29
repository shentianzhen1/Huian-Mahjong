import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from types import SimpleNamespace
from workspace.hint_alpha.video_test import run_video_test
from tests.test_live_snapshot_stability import burst

class VideoReferencePolicyTests(unittest.TestCase):
    def test_trial_pipeline_is_shared_and_confirms_current_hand(self):
        seen=[]
        def evaluate(samples, **kwargs):
            pipeline=kwargs['pipeline'];seen.append(pipeline)
            result=pipeline.evaluate(burst(samples[-1][0]),captured=samples[-1][1],experimental=True)
            self.assertEqual(result.display_allowed,len(seen)>1)
            self.assertFalse(result.safe_for_executor)
            return dict(display_allowed=result.display_allowed,frames=[x[0] for x in samples],
                source_seconds=[x[1] for x in samples],snapshot={'hand_trusted':False,'own_hand':[],'gold_trusted':False,'gold_tile':None},
                hint={'phase':None,'best_discards':[],'issues':[]})
        reader=SimpleNamespace(read_window=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('no OCR')))
        with TemporaryDirectory() as tmp, patch('workspace.hint_alpha.video_test.probe_video',return_value={'fps':30,'duration_seconds':1,'width':1108,'height':512}), patch('workspace.hint_alpha.video_test.iter_video_samples',return_value=iter([(i,i*.2,object()) for i in range(1,7)])) as sampler, patch('workspace.hint_alpha.video_test.evaluate_burst',side_effect=evaluate):
            video=Path(tmp)/'v.mp4';video.write_bytes(b'test')
            run_video_test(video,dataset_root='unused',reference_packet='explicit.json',public_reader=reader)
            self.assertEqual(sampler.call_args.kwargs['sample_interval_seconds'], .2)
        self.assertEqual(len(seen),2)
        self.assertIs(seen[0],seen[1])
        self.assertTrue(seen[0].allow_unvalidated_hand_sources)

    def test_within_burst_confirms_two_frames_but_not_unknown_current(self):
        from copy import deepcopy
        from workspace.hint_alpha.replay_smoke import evaluate_burst
        from workspace.hint_alpha.runtime_pipeline import RuntimeAdvicePipeline
        from workspace.hint_alpha.live_snapshot_stability import LiveSnapshotStability
        for unknown in (False, True):
            def reader(images, root, *, identity_frame_id=None, **kwargs):
                report=deepcopy(burst(3))
                if identity_frame_id is not None:
                    for item in report['components']:
                        item['frame']=identity_frame_id
                elif unknown:
                    report['components'][0]['tile_id']='UNKNOWN'
                    report['components'][0]['identity_reason']='score_below_threshold'
                return report
            pipeline=RuntimeAdvicePipeline(stability_tracker=LiveSnapshotStability())
            samples=[(i,i*.2,SimpleNamespace(tobytes=lambda: b'pixels')) for i in (1,2,3)]
            result=evaluate_burst(samples,session='runtime-live',dataset_root='unused',reader=reader,pipeline=pipeline,confirm_with_prior=True)
            self.assertEqual(result['display_allowed'],not unknown)
            self.assertFalse(result['safe_for_executor'])

    def test_fresh_confirmed_hand_resets_before_current_advice(self):
        from dataclasses import dataclass
        @dataclass
        class Observation:
            hand_number: int
            hand_votes: int = 2
            score_pair: object = None
        for hands, expected in [([2,3,3], [1,2,2]), ([2,5,3], [1,1,2]),
                                ([2,1,2], [1,1,1])]:
            calls=[]
            reader=SimpleNamespace(read_window=lambda *a,**k: SimpleNamespace(
                observation=Observation(hands[len(calls)])))
            def evaluate(samples, **kwargs):
                calls.append(reset.call_count)
                return dict(display_allowed=False,frames=[x[0] for x in samples],
                    source_seconds=[x[1] for x in samples],
                    snapshot={'hand_trusted':False,'own_hand':[], 'gold_trusted':False,'gold_tile':None},
                    hint={'phase':None,'best_discards':[],'issues':[]})
            with TemporaryDirectory() as tmp, \
                 patch('workspace.hint_alpha.video_test.probe_video',return_value={'fps':30,'duration_seconds':8,'width':1108,'height':512}), \
                 patch('workspace.hint_alpha.video_test.iter_video_samples',return_value=iter([(i,float(i),object()) for i in range(7)])), \
                 patch('workspace.hint_alpha.video_test.evaluate_burst',side_effect=evaluate), \
                 patch('workspace.hint_alpha.runtime_pipeline.RuntimeAdvicePipeline.reset') as reset:
                video=Path(tmp)/'v.mp4';video.write_bytes(b'test')
                run_video_test(video,dataset_root='unused',reference_packet='explicit.json',public_reader=reader)
            self.assertEqual(calls,expected)

    def test_pending_hand_retries_ocr_without_lowering_consensus(self):
        from dataclasses import dataclass
        @dataclass
        class Observation:
            hand_number: object
            hand_votes: int = 2
            score_pair: object = None
        reads=[]
        sequence=iter([Observation(2), Observation(None,1), Observation(None,1), Observation(3)])
        def read(images, **kwargs):
            reads.append(len(reads))
            return SimpleNamespace(observation=next(sequence))
        reset_counts=[]
        def evaluate(samples, **kwargs):
            reset_counts.append(reset.call_count)
            return dict(display_allowed=False,frames=[x[0] for x in samples],
                source_seconds=[x[1] for x in samples],
                snapshot={'hand_trusted':False,'own_hand':[], 'gold_trusted':False,'gold_tile':None},
                hint={'phase':None,'best_discards':[],'issues':[]})
        with TemporaryDirectory() as tmp, \
             patch('workspace.hint_alpha.video_test.probe_video',return_value={'fps':30,'duration_seconds':6,'width':1108,'height':512}), \
             patch('workspace.hint_alpha.video_test.iter_video_samples',return_value=iter([(i,i*.5,object()) for i in range(11)])), \
             patch('workspace.hint_alpha.video_test.evaluate_burst',side_effect=evaluate), \
             patch('workspace.hint_alpha.runtime_pipeline.RuntimeAdvicePipeline.reset') as reset:
            video=Path(tmp)/'v.mp4';video.write_bytes(b'test')
            run_video_test(video,dataset_root='unused',reference_packet='explicit.json',
                           public_reader=SimpleNamespace(read_window=read))
        self.assertEqual(len(reads),4)
        self.assertEqual(reset_counts,[1,1,1,1,2])
