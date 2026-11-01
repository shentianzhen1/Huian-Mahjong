import hashlib
import json
from pathlib import Path
import tempfile
import unittest

try:
    import cv2
    import numpy as np
    from PIL import Image
    from workspace.vision.tiles_v0_1.template_classifier import Classification, _feature
except ImportError:
    cv2 = None


@unittest.skipUnless(cv2 is not None, 'Vision dependencies unavailable')
class ExperimentalHandTranslationTests(unittest.TestCase):
    def test_translation_recovers_shifted_reference_without_changing_confident_read(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from workspace.vision.tiles_runtime_v0_2.experimental_hand_translation import TranslatedHandClassifier
        pixels = np.full((72, 48, 3), 220, np.uint8)
        pixels[18:57, 15:20] = (20, 90, 20)
        image = Image.fromarray(pixels)
        query = _feature(image, region='concealed_identity')
        padded = cv2.copyMakeBorder(query, 3, 3, 3, 3, cv2.BORDER_REPLICATE)
        reference = padded[3:75, 5:53].copy()
        ordinary = SimpleNamespace(classify=Mock(return_value=Classification('S7', .6)),
                                   regional_templates={'concealed_identity': {}})
        adapter = TranslatedHandClassifier(ordinary, [('S9', reference)])
        result = adapter.classify(image, region='concealed_identity')
        self.assertEqual(result.tile_id, 'S9')
        self.assertAlmostEqual(result.confidence, 1., places=5)
        ordinary.classify.return_value = Classification('S3', .9)
        self.assertIs(adapter.classify(image, region='concealed_identity'), ordinary.classify.return_value)

    def test_public_and_yellow_gold_roles_delegate(self):
        from unittest.mock import Mock
        from workspace.vision.tiles_runtime_v0_2.experimental_hand_translation import TranslatedHandClassifier
        ordinary = Mock()
        ordinary.classify.return_value = Classification('M4', .4)
        adapter = TranslatedHandClassifier(ordinary, [])
        image = Image.new('RGB', (48,72), 'white')
        self.assertIs(adapter.classify(image, region='gold_region'), ordinary.classify.return_value)
        adapter.classify_gold_skin(image)
        ordinary.classify_gold_skin.assert_called_once_with(image)

    def test_packet_hash_and_resource_copy(self):
        from workspace.vision.tiles_runtime_v0_2.experimental_hand_translation import with_private_hand_packet
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = Image.new('RGB', (48,72), 'white')
            image.save(root/'ref.png')
            row = dict(truth='S3',crop='ref.png',rgb_sha256=hashlib.sha256(image.tobytes()).hexdigest())
            manifest = root/'manifest.json'
            manifest.write_text(json.dumps(dict(rows=[row])))
            ordinary = object()
            resources = dict(classifier=ordinary, coverage=object())
            copied = with_private_hand_packet(resources, manifest)
            self.assertIs(resources['classifier'], ordinary)
            self.assertIs(copied['coverage'], resources['coverage'])
            row['rgb_sha256'] = '0'*64
            manifest.write_text(json.dumps(dict(rows=[row])))
            with self.assertRaisesRegex(ValueError, 'RGB mismatch'):
                with_private_hand_packet(resources, manifest)
