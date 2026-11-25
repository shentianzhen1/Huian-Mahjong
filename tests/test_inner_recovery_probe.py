import unittest
from types import SimpleNamespace
from unittest.mock import Mock
try:
    import cv2
    import numpy as np
    from PIL import Image
except ImportError:
    cv2 = None
from workspace.vision.tiles_runtime_v0_2.inner_recovery_probe import InnerRecoveryProbe

@unittest.skipUnless(cv2 is not None, 'Vision dependencies unavailable')
class InnerRecoveryProbeTests(unittest.TestCase):
    def test_opt_in_recovery_preserves_original_and_other_roles(self):
        from workspace.vision.tiles_runtime_v0_2.neutral_face_feature_probe import neutral
        from workspace.vision.tiles_v0_1.template_classifier import Classification
        pixels=np.full((80,50,3),230,np.uint8)
        pixels[15:35,10:20]=0;pixels[45:65,28:40]=30
        image=Image.fromarray(pixels)
        prediction=Classification('M3', .7)
        source=SimpleNamespace(classify=Mock(return_value=prediction),inner_features=[('M5',neutral(image,trim_edges=True))])
        candidate=InnerRecoveryProbe(source)
        self.assertEqual(candidate.classify(image,'concealed_identity').tile_id,'M5')
        self.assertIs(candidate.classify(image,'gold_region'),prediction)
        source.classify.return_value=Classification('M3',.9)
        self.assertIs(candidate.classify(image,'concealed_identity'),source.classify.return_value)
        self.assertIs(candidate.ordinary,source)
        source.classify.return_value=prediction;source.inner_features=[]
        self.assertIs(candidate.classify(image,'concealed_identity'),prediction)
