"""Real source-checked sparse screenshots exercise abstention, not acceptance."""
from collections import deque
import importlib.util
import json
from pathlib import Path
import unittest

from workspace.hint_alpha.replay_smoke import evaluate_burst, manifest_samples


@unittest.skipUnless(importlib.util.find_spec('cv2') and importlib.util.find_spec('PIL'),
                     'optional real-frame Vision dependencies unavailable')
class RealSparseFrameSmokeTests(unittest.TestCase):
    def test_source_locked_real_pixels_abstain_without_live_stability(self):
        root = Path(__file__).resolve().parents[1]
        source = root / 'references/gameplay/2026-09-15/66fe863f_youjin100/source.json'
        metadata = json.loads(source.read_text())
        frozen = json.loads((root / 'references/vision/2026-10-04/alpha_sparse_real_frame_abstention_v0_1.json').read_text())
        self.assertEqual(frozen['source_sha256'], metadata['source_sha256'])
        self.assertFalse(frozen['formal_promotion_evidence'])
        window = deque(maxlen=3)
        results = []
        for sample in manifest_samples(source):
            window.append(sample)
            if len(window) == 3:
                results.append(evaluate_burst(tuple(window), session=metadata['evidence_id'],
                                             dataset_root=root / 'dataset/tiles_runtime_v0_2'))
        self.assertEqual(len(results), 10)
        for actual, expected in zip(results, frozen['rows']):
            self.assertEqual(actual['pixel_sha256'], expected['pixel_sha256'])
            self.assertEqual(actual['frames'], expected['frames'])
            self.assertFalse(actual['display_allowed'])
            self.assertFalse(actual['hint']['allowed'])
            self.assertTrue(actual['sparse_source_burst'])
            self.assertFalse(actual['safe_for_executor'])
