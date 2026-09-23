"""Real-video probe contracts; synthetic video is not real accuracy evidence."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from workspace.vision.real_video_public_probe import probe_video, source_sha256


class RealPublicVideoProbeTests(unittest.TestCase):
    def test_hash_gate_rejects_other_video_before_any_predictions(self):
        with tempfile.TemporaryDirectory() as temp:
            video = Path(temp) / 'unrelated.mp4'
            video.write_bytes(b'different video')
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                probe_video(
                    video, source_session='s1', expected_sha256='a' * 64,
                    first_frame=0, last_frame=10,
                    profile_manifest=Path(temp) / 'missing.json',
                )

    def test_scope_input_requires_source_session_hash_and_positive_span(self):
        with tempfile.TemporaryDirectory() as temp:
            video = Path(temp) / 'binary.mp4'
            video.write_bytes(b'fake bytes')
            digest = hashlib.sha256(b'fake bytes').hexdigest()
            self.assertEqual(source_sha256(video), digest)
            for fields in (
                {'source_session': ''},
                {'expected_sha256': digest.upper()},
                {'first_frame': 4, 'last_frame': 4},
                {'first_frame': -1},
            ):
                kwargs = dict(
                    source_session='session', expected_sha256=digest,
                    first_frame=0, last_frame=4,
                    profile_manifest=Path(temp) / 'missing.json',
                )
                kwargs.update(fields)
                with self.assertRaises(ValueError):
                    probe_video(video, **kwargs)

    @unittest.skipUnless(importlib.util.find_spec('cv2') is not None, 'Vision optional dependency')
    def test_synthetic_video_produces_tracks_but_never_claims_actions(self):
        import cv2
        import numpy as np
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            video = directory / 'synthetic.avi'
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'MJPG'), 10.0, (128, 72))
            if not writer.isOpened():
                self.skipTest('OpenCV MJPG writer unavailable')
            for i in range(14):
                image = np.zeros((72, 128, 3), dtype=np.uint8)
                if i >= 3:
                    cv2.rectangle(image, (24, 12), (30, 24), (245, 245, 245), -1)
                writer.write(image)
            writer.release()
            manifest = directory / 'profiles.json'
            manifest.write_text(json.dumps({
                'schema_version': 'public_channel_profiles_v0_1',
                'excluded_from_formal_promotion': True,
                'development_only_reason': 'synthetic contract test only',
                'profiles': [{
                    'name': 'bright_square_dev',
                    'geometry_kinds': ['single_face'],
                    'zones': [[0.1, 0.1, 0.5, 0.5]],
                    'minimum_zone_coverage': 0.7,
                    'semantic_scope': 'unqualified_geometry',
                    'actor_policy': 'external',
                    'action_policy': 'external',
                    'development_only': True,
                    'evidence_sample_ids': ['synthetic'],
                }],
            }), encoding='utf-8')
            result = probe_video(
                video, source_session='synthetic', expected_sha256=source_sha256(video),
                first_frame=0, last_frame=13, profile_manifest=manifest,
            )
            self.assertEqual(result['frames_decoded'], 14)
            self.assertEqual(result['stream_epochs'], [0])
            self.assertGreaterEqual(result['counts']['APPEARED'], 1)
            self.assertEqual(result['profile_appearances']['bright_square_dev'], 1)
            self.assertEqual(result['reconstructed_actions'], [])
            self.assertIsNone(result['action_metric'])
            self.assertFalse(result['formal_promotion_evidence'])
            self.assertFalse(result['safe_for_executor'])


if __name__ == '__main__':
    unittest.main()
