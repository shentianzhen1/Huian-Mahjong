import math
import unittest
from workspace.vision.tiles_runtime_v0_2.gold_score_calibration import FEATURE_NAMES, probability

try:
    import cv2
    import numpy as np
    from workspace.vision.tiles_runtime_v0_2.gold_score_calibration import geometry_evidence
except ImportError:
    cv2 = np = None


class GoldScoreProbabilityTests(unittest.TestCase):
    def test_unknown_is_zero_and_large_logits_remain_finite(self):
        model=dict(feature_names=list(FEATURE_NAMES),coef=[1.0]*len(FEATURE_NAMES),
                   intercept=0.,mean=[0.]*len(FEATURE_NAMES),scale=[1.]*len(FEATURE_NAMES))
        self.assertEqual(probability([1000.]*len(FEATURE_NAMES),model,candidate='UNKNOWN'),0.)
        self.assertEqual(probability([1000.]*len(FEATURE_NAMES),model,candidate='M4'),1.)
        self.assertEqual(probability([-1000.]*len(FEATURE_NAMES),model,candidate='M4'),0.)
        self.assertEqual(probability([0.]*len(FEATURE_NAMES),model,candidate='M4'),0.5)


@unittest.skipUnless(cv2 is not None and np is not None,'Vision dependencies unavailable')
class GoldScoreGeometryTests(unittest.TestCase):
    def setUp(self):
        self.points=np.float32([(10,10),(45,10),(80,10),(10,45),(80,45),(10,80),(45,80),(80,80)])
        self.descriptors=np.eye(8,128,dtype=np.float32)

    def test_consistent_transform_has_more_inliers_than_scrambled_positions(self):
        query=(self.points,self.descriptors,(100,100))
        target=self.points*1.3+np.float32([8,15])
        consistent=geometry_evidence(query,(target,self.descriptors,(150,150)))
        scrambled=geometry_evidence(query,(target[[2,6,0,7,3,1,5,4]],self.descriptors,(150,150)))
        self.assertEqual(consistent['inliers'],8)
        self.assertEqual(consistent['unique_matches'],8)
        self.assertGreater(consistent['inlier_ratio'],scrambled['inlier_ratio'])

    def test_repeated_target_feature_is_not_independent_support(self):
        query=(self.points,np.repeat(self.descriptors[:1],8,axis=0),(100,100))
        result=geometry_evidence(query,(self.points,self.descriptors,(100,100)))
        self.assertEqual(result['unique_matches'],1)
        self.assertEqual(result['inliers'],0)
        self.assertEqual(result['unique_ratio'],1/8)

    def test_missing_descriptors_are_no_geometric_evidence(self):
        result=geometry_evidence((self.points,None,(100,100)),(self.points,self.descriptors,(100,100)))
        self.assertEqual(result['inliers'],0)
        self.assertEqual(result['unique_matches'],0)


class GoldScoreAdapterTests(unittest.TestCase):
    def test_scoring_is_only_for_opened_indicator_not_playable_gold_hand(self):
        from types import SimpleNamespace
        from unittest.mock import Mock,patch
        from workspace.vision.tiles_runtime_v0_2.gold_score_calibration import GoldOnlyScoredClassifier
        ordinary=Mock()
        ordinary.classify.return_value='ordinary-hand'
        ordinary.classify_gold_skin.return_value='playable-yellow-hand'
        gold=Mock()
        gold.classify.return_value=SimpleNamespace(tile_id='M4')
        model=dict(feature_names=list(FEATURE_NAMES),coef=[0.]*len(FEATURE_NAMES),
                   intercept=2.,mean=[0.]*len(FEATURE_NAMES),scale=[1.]*len(FEATURE_NAMES))
        adapter=GoldOnlyScoredClassifier(ordinary,gold,model)
        self.assertEqual(adapter.classify('pixels',region='concealed_identity'),'ordinary-hand')
        self.assertEqual(adapter.classify_gold_skin('yellow-pixels'),'playable-yellow-hand')
        gold.classify.assert_not_called()
        with patch('workspace.vision.tiles_runtime_v0_2.gold_score_calibration.evidence_features',return_value=([0.]*len(FEATURE_NAMES),{})):
            try:
                result=adapter.classify_opened_gold('indicator-pixels')
            except ImportError:
                self.skipTest('Vision dependencies unavailable')
        self.assertEqual(result.tile_id,'M4')
        self.assertAlmostEqual(result.confidence,1/(1+math.exp(-2)))


@unittest.skipUnless(cv2 is not None and np is not None,'Vision dependencies unavailable')
class GoldScoreRuntimeRoleTests(unittest.TestCase):
    def test_runtime_only_sends_explicit_indicator_to_new_scoring_method(self):
        from PIL import Image
        from workspace.vision.tiles_runtime_v0_2.dynamic_geometry import GeometryComponent
        from workspace.vision.tiles_runtime_v0_2.runtime_reader import _classify_runtime_component,GOLD_IDENTITY_GATE_REGION
        from workspace.vision.tiles_v0_1.template_classifier import Classification
        calls=[]
        class Classifier:
            def classify_opened_gold(self,image):
                calls.append('opened');return Classification('M4',0.93)
            def classify_gold_skin(self,image):
                calls.append('playable');return Classification('M6',0.91)
        covered={*(f'{s}{i}' for s in 'MPS' for i in range(1,10)),'E','SOUTH','W','N','R','G','B'}
        for region,expected in [('gold','M4'),('hand','M6')]:
            component=GeometryComponent((20,20,40,60),(0.2,0.2,0.4,0.6),region,0.9,1,'test',True)
            result=_classify_runtime_component(component,Image.new('RGB',(120,120),'white'),
                all_boxes=[component.pixel_bbox],classifier=Classifier(),
                covered_by_region={GOLD_IDENTITY_GATE_REGION:covered},
                cross_session={GOLD_IDENTITY_GATE_REGION:{'M4','M6'}},
                confidence_threshold=0.82,gold_skin_covered={'M4','M6'})
            self.assertEqual(result['tile_id'],expected)
        self.assertEqual(calls,['opened','playable'])
