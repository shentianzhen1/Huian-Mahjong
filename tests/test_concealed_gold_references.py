import unittest
from types import SimpleNamespace
from unittest.mock import Mock
try:
    import numpy as np
    from PIL import Image
    from workspace.vision.tiles_v0_1.template_classifier import _feature, Classification
except ImportError:
    np = None
from workspace.vision.tiles_runtime_v0_2.concealed_gold_references import ConcealedGoldReferenceClassifier


@unittest.skipUnless(np is not None, 'Vision dependencies unavailable')
class ConcealedGoldReferenceTests(unittest.TestCase):
    def setUp(self):
        pixels = np.full((75,52,3), (220,190,60), np.uint8)
        pixels[15:50,15:22] = 20
        self.image = Image.fromarray(pixels)
        self.ref = _feature(self.image, region='gold_region')
        self.original = SimpleNamespace(
            classify_gold_skin=Mock(return_value=Classification('SOUTH', .72)),
            classify=Mock(return_value=Classification('N', .7)),
            classify_opened_gold=Mock(return_value=Classification('M4', .3)))

    def test_agreeing_reference_recovers_only_concealed_gold(self):
        c = ConcealedGoldReferenceClassifier(self.original, [('SOUTH',self.ref)])
        self.assertEqual(c.classify_gold_skin(self.image).tile_id, 'SOUTH')
        self.assertGreater(c.classify_gold_skin(self.image).confidence, .99)
        self.assertEqual(c.classify_opened_gold(self.image), Classification('M4',.3))
        self.assertEqual(c.classify(self.image), Classification('N',.7))

    def test_missing_or_ambiguous_reference_does_not_guess(self):
        for refs in [[], [('M4',self.ref)], [('SOUTH',self.ref),('M4',self.ref)]]:
            c = ConcealedGoldReferenceClassifier(self.original, refs)
            self.assertEqual(c.classify_gold_skin(self.image), Classification('SOUTH',.72))

    def test_confident_original_is_preserved(self):
        self.original.classify_gold_skin.return_value = Classification('M4',.9)
        c = ConcealedGoldReferenceClassifier(self.original, [('SOUTH',self.ref)])
        self.assertEqual(c.classify_gold_skin(self.image), Classification('M4',.9))

    def test_explicit_packet_role_keeps_source_gates_and_ordinary_banks(self):
        import json, hashlib, shutil, tempfile
        from pathlib import Path
        from workspace.vision.tiles_runtime_v0_2.runtime_reader import prepare_runtime_resources
        from workspace.vision.tiles_runtime_v0_2.experimental_hand_translation import with_private_hand_packet
        root = Path(__file__).resolve().parents[1]/'dataset/tiles_runtime_v0_2'
        raw = prepare_runtime_resources(root)
        original_coverage = set(raw['gold_skin_covered'])
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)/'packet'
            shutil.copytree(root/'reference_pack', folder)
            self.image.save(folder/'concealed_gold.png')
            path = folder/'selected.json'
            manifest = json.loads(path.read_text())
            manifest['rows'].append(dict(role='concealed_gold', truth='SOUTH',
                crop='concealed_gold.png', rgb_sha256=hashlib.sha256(self.image.tobytes()).hexdigest()))
            path.write_text(json.dumps(manifest))
            result = with_private_hand_packet(raw, path)
        c = result['classifier']
        self.assertEqual(len(c.extra_features),16)
        self.assertEqual(c.opened_gold_reference_count,3)
        self.assertEqual(result['gold_skin_covered'],original_coverage)
        self.assertEqual(raw['gold_skin_covered'],original_coverage)
        self.assertIsInstance(c.ordinary, ConcealedGoldReferenceClassifier)

    def test_small_crop_shift_recovers_without_changing_identity(self):
        from unittest.mock import patch
        rng = np.random.default_rng(10)
        reference = rng.normal(size=(20,16)).astype(np.float32)
        query = np.roll(reference, 1, axis=1)
        c = ConcealedGoldReferenceClassifier(self.original, [('SOUTH',reference)])
        with patch('workspace.vision.tiles_v0_1.template_classifier._feature', return_value=query):
            result = c.classify_gold_skin(None)
            self.assertEqual(result.tile_id, 'SOUTH')
            self.assertGreater(result.confidence, .9)
            self.original.classify_gold_skin.return_value = Classification('M4',.72)
            self.assertEqual(c.classify_gold_skin(None), Classification('M4',.72))
