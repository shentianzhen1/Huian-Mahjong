import unittest
try:
    import numpy as np
    from PIL import Image
    from workspace.vision.tiles_v0_1.template_classifier import TemplateTileClassifier, _feature
    from workspace.vision.tiles_runtime_v0_2.batched_ordinary_classifier import BatchedOrdinaryClassifier
except ImportError:
    np = None


@unittest.skipUnless(np is not None, 'Vision dependencies unavailable')
class BatchedOrdinaryClassifierTests(unittest.TestCase):
    def test_real_feature_transform_matches_opencv_scores_and_labels(self):
        rng=np.random.default_rng(804)
        images=[Image.fromarray(rng.integers(0,256,(80,52,3),dtype=np.uint8)) for _ in range(8)]
        bank={str(i):[_feature(im)] for i,im in enumerate(images)}
        ordinary=TemplateTileClassifier(bank,{'concealed_identity':bank})
        fast=BatchedOrdinaryClassifier(ordinary)
        queries=images+[Image.fromarray(rng.integers(0,256,(80,52,3),dtype=np.uint8)) for _ in range(20)]
        queries.append(Image.new('RGB',(52,80),'white'))
        for image in queries:
            expected=ordinary.classify(image,region='concealed_identity')
            actual=fast.classify(image,region='concealed_identity')
            self.assertEqual(actual.tile_id,expected.tile_id)
            self.assertAlmostEqual(actual.confidence,expected.confidence,delta=2e-6)
            self.assertEqual(actual.confidence>=.82,expected.confidence>=.82)

    def test_ties_and_constant_template_follow_opencv(self):
        image=Image.new('RGB',(48,72),'white');feature=_feature(image)
        bank={'B':[feature],'P2':[feature]}
        ordinary=TemplateTileClassifier(bank,{'concealed_identity':bank})
        actual=BatchedOrdinaryClassifier(ordinary).classify(image,region='concealed_identity')
        self.assertEqual(actual,ordinary.classify(image,region='concealed_identity'))

    def test_threshold_boundary_falls_back_to_original_opencv(self):
        from unittest.mock import Mock, patch
        from workspace.vision.tiles_v0_1.template_classifier import Classification
        ref=np.zeros((72,48),np.float32);ref[0,0]=1;ref[0,1]=-1
        orth=np.zeros_like(ref);orth[0,2]=1;orth[0,3]=-1
        query=.82*ref+np.sqrt(1-.82**2)*orth
        bank={'M1':[ref]}
        ordinary=TemplateTileClassifier(bank,{'concealed_identity':bank})
        expected=Classification('M1',.8199999)
        ordinary.classify=Mock(return_value=expected)
        fast=BatchedOrdinaryClassifier(ordinary)
        with patch('workspace.vision.tiles_runtime_v0_2.batched_ordinary_classifier._feature',return_value=query):
            actual=fast.classify(Image.new('RGB',(48,72)),region='concealed_identity')
        self.assertIs(actual,expected)
        ordinary.classify.assert_called_once()
