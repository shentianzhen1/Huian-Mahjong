"""Synthetic source-frame samples: never require private real recordings in CI."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

AVAILABLE = all(importlib.util.find_spec(x) is not None for x in ('cv2','numpy','PIL'))

@unittest.skipUnless(AVAILABLE, 'Vision extras optional')
class PublicReviewSampleTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.video=self.root/'source.mp4'; self.video.write_bytes(b'synthetic input')
        self.sha=hashlib.sha256(self.video.read_bytes()).hexdigest()
        self.registry=self.root/'registry.json'
        self.registry.write_text(json.dumps({'schema_version':'public_source_lineage_v0_1','sources':[
            dict(source_session='synthetic_archived', source_sha256=self.sha,
                 match_group='test_match', capture_mode='in_app_replay',
                 review_exposure='previously_inspected', development_only=True,
                 excluded_from_formal_promotion=True)]}))
        self.manifest=self.root/'manifest.json'
        self.manifest.write_text(json.dumps({'schema_version':'source_public_review_samples_v0_1',
            'source_session':'synthetic_archived','source_sha256':self.sha,
            'frame_size':[1046,480], 'development_only':True,
            'excluded_from_formal_promotion':True,'samples':[
            dict(sample_id='upper_one',frame=4,pixel_bbox=[646,111,27,30],
                 screen_side_actor='opponent',region='public_single')]}))

    def capture(self):
        import cv2
        import numpy as np
        class Capture:
            released=False
            def isOpened(self):return True
            def get(self,p):
                return {cv2.CAP_PROP_FRAME_WIDTH:1046,cv2.CAP_PROP_FRAME_HEIGHT:480}[p]
            def set(self,p,v):return p==cv2.CAP_PROP_POS_FRAMES
            def read(self):
                frame=np.zeros((480,1046,3),dtype=np.uint8)
                frame[111:141,646:673]=(255,255,255)
                return True,frame
            def release(self):self.released=True
        return Capture()

    def test_private_unlabeled_pixel_verified_output(self):
        import cv2
        from workspace.vision.source_public_review_samples import export_review_samples
        fake=self.capture()
        with patch.object(cv2,'VideoCapture',return_value=fake):
            result=export_review_samples(video=self.video,manifest_path=self.manifest,
                          registry_path=self.registry,output_dir=self.root/'private')
        self.assertTrue(fake.released)
        self.assertEqual(len(result['samples']),1)
        self.assertIsNone(result['samples'][0]['tile_id'])
        self.assertTrue(result['samples'][0]['crop_pixels_verified'])
        self.assertFalse(result['formal_promotion_evidence'])
        self.assertFalse(result['safe_for_executor'])

    def test_wrong_hash_fails_before_decode(self):
        import cv2
        from workspace.vision.source_public_review_samples import export_review_samples
        self.video.write_bytes(b'mutated')
        with patch.object(cv2,'VideoCapture',side_effect=AssertionError('decoded before hash')):
            with self.assertRaisesRegex(ValueError,'SHA256 mismatch'):
                export_review_samples(video=self.video,manifest_path=self.manifest,
                      registry_path=self.registry, output_dir=self.root/'private')

    def test_public_checkout_and_bad_boxes_rejected(self):
        from workspace.vision.source_public_review_samples import export_review_samples
        with self.assertRaisesRegex(ValueError,'outside repository'):
            export_review_samples(video=self.video,manifest_path=self.manifest,
                registry_path=self.registry,output_dir=Path(__file__).resolve().parents[1]/'unsafe_crops')
        data=json.loads(self.manifest.read_text())
        data['samples'][0]['pixel_bbox']=[1040,470,50,50]
        self.manifest.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'outside source'):
            export_review_samples(video=self.video,manifest_path=self.manifest,
                registry_path=self.registry, output_dir=self.root/'private')

if __name__ == '__main__':unittest.main()
