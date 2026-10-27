import unittest
from types import SimpleNamespace
from unittest.mock import Mock
try:
    import numpy as np
    from PIL import Image
    from workspace.vision.tiles_v0_1.template_classifier import _feature, Classification
    from workspace.vision.tiles_runtime_v0_2.opened_gold_references import OpenedGoldReferenceClassifier
except ImportError:
    np=None


@unittest.skipUnless(np is not None, 'Vision dependencies unavailable')
class OpenedGoldReferenceTests(unittest.TestCase):
    def test_disagreement_and_hand_gold_skin_never_use_opened_reference_override(self):
        pixels=np.full((57,42,3),(220,190,60),np.uint8)
        pixels[15:40,13:20]=(30,30,30)
        image=Image.fromarray(pixels)
        ordinary=SimpleNamespace(classify_gold_skin=Mock(return_value=Classification('M4',.3)))
        classifier=OpenedGoldReferenceClassifier(ordinary,[('M6',_feature(image,region='gold_region'))])
        self.assertEqual(classifier.classify_opened_gold(image),Classification('M4',.3))
        self.assertFalse(classifier.opened_gold_reference_supported(image,Classification('M4',.3)))
        ordinary.classify_gold_skin.return_value=Classification('M6',.3)
        recovered=classifier.classify_opened_gold(image)
        self.assertEqual(recovered.tile_id,'M6')
        self.assertGreater(recovered.confidence,.99)
        self.assertTrue(classifier.opened_gold_reference_supported(image,recovered))
        self.assertEqual(classifier.classify_gold_skin(image),Classification('M6',.3))
        ordinary.classify_gold_skin.return_value=Classification('M4',.9)
        self.assertEqual(classifier.classify_opened_gold(image),Classification('M4',.9))

    def test_bundled_gold_references_do_not_pollute_hand_features(self):
        from pathlib import Path
        from workspace.vision.tiles_runtime_v0_2.runtime_reader import prepare_runtime_resources
        from workspace.vision.tiles_runtime_v0_2.experimental_hand_translation import with_private_hand_packet
        root=Path(__file__).resolve().parents[1]/'dataset/tiles_runtime_v0_2'
        resources=with_private_hand_packet(prepare_runtime_resources(root),root/'reference_pack/selected.json')
        self.assertEqual(len(resources['classifier'].extra_features),16)
        self.assertEqual(resources['classifier'].opened_gold_reference_count,3)
        self.assertNotIn('M4',resources['gold_skin_covered'])  # strict qualification unchanged

    def test_represented_competing_class_can_be_rejected_without_guessing_missing_classes(self):
        ordinary=SimpleNamespace(classify_gold_skin=Mock(return_value=Classification('M1',.37)))
        classifier=OpenedGoldReferenceClassifier(ordinary,[])
        classifier._scores=Mock(return_value=[('M4',.98),('M1',.72),('M6',.76)])
        self.assertEqual(classifier.classify_opened_gold(None),Classification('M4',.98))
        for scores in [ [('M4',.98),('M6',.76)], [('M4',.98),('M1',.83)], [('M4',.98),('M1',.72),('M6',.84)], [('M4',.81),('M1',.72)]]:
            with self.subTest(scores=scores):
                classifier._scores.return_value=scores
                self.assertEqual(classifier.classify_opened_gold(None),Classification('M1',.37))
