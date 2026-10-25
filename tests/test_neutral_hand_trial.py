import unittest
from types import SimpleNamespace
from unittest.mock import Mock

try:
    import numpy as np
    from PIL import Image
    from workspace.vision.tiles_v0_1.template_classifier import Classification
    from workspace.vision.tiles_runtime_v0_2.experimental_hand_translation import TranslatedHandClassifier
    from workspace.vision.tiles_runtime_v0_2.neutral_face_feature_probe import neutral
except ImportError:
    np = None



@unittest.skipUnless(np is not None, 'Vision dependencies unavailable')
class NeutralHandTrialTests(unittest.TestCase):
    def test_only_matching_low_score_ordinary_prediction_is_recovered(self):
        pixels = np.full((80, 50, 3), 230, np.uint8)
        pixels[15:32, 10:22] = (10, 70, 10)
        pixels[45:65, 27:40] = (10, 70, 10)
        image = Image.fromarray(pixels)
        ordinary = SimpleNamespace(classify=Mock(return_value=Classification('P2', .6)),
                                   regional_templates={'concealed_identity': {}})
        adapter = TranslatedHandClassifier(ordinary, [], [('P2', neutral(image))])
        self.assertGreater(adapter.classify(image, 'concealed_identity').confidence, .99)
        adapter.neutral_features = [('M3', neutral(image))]
        self.assertEqual(adapter.classify(image, 'concealed_identity').tile_id, 'P2')
        self.assertEqual(adapter.classify(image, 'concealed_identity').confidence, .6)
        confident = Classification('S4', .9)
        ordinary.classify.return_value = confident
        self.assertIs(adapter.classify(image, 'concealed_identity'), confident)
        self.assertIs(adapter.classify(image, 'gold_region'), confident)

    def test_inner_fallback_preserves_first_recovery_and_requires_agreement(self):
        pixels = np.full((80, 50, 3), 230, np.uint8)
        pixels[15:35, 10:20] = (10, 70, 10)
        pixels[45:65, 28:40] = (10, 70, 10)
        image = Image.fromarray(pixels)
        ordinary = SimpleNamespace(classify=Mock(return_value=Classification('P2', .6)),
                                   regional_templates={'concealed_identity': {}})
        adapter = TranslatedHandClassifier(ordinary, [], [], [('P2', neutral(image, trim_edges=True))])
        self.assertGreater(adapter.classify(image, 'concealed_identity').confidence, .99)
        adapter.inner_features = [('M3', neutral(image, trim_edges=True))]
        self.assertEqual(adapter.classify(image, 'concealed_identity').confidence, .6)
        adapter.neutral_features = [('P2', neutral(image))]
        self.assertGreater(adapter.classify(image, 'concealed_identity').confidence, .99)
