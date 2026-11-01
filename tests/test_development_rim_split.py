import unittest
try:
    import numpy as np
    from workspace.vision.tiles_runtime_v0_2.development_cluster_geometry import _split_joined_component
except ImportError:
    _split_joined_component = None

@unittest.skipIf(_split_joined_component is None, "Vision dependencies required")
class RimSplitTests(unittest.TestCase):
    def test_equal_depth_rim_uses_nominal_boundary_not_left_bias(self):
        mask=np.ones((70,100),dtype=np.uint8)*255
        mask[:10,49:51]=0
        self.assertEqual([b[2] for b in _split_joined_component((0,0,100,70),mask,50)],[50,50])

    def test_rim_seam_beats_dark_artwork(self):
        mask = np.ones((70,100),dtype=np.uint8)*255
        mask[:10,50]=0
        mask[10:,60]=0
        boxes=_split_joined_component((0,0,100,70),mask,50)
        self.assertEqual([b[2] for b in boxes],[50,50])

    def test_no_rim_contrast_retains_original_projection(self):
        mask=np.ones((70,100),dtype=np.uint8)*255
        mask[10:,52]=0
        self.assertEqual([b[2] for b in _split_joined_component((0,0,100,70),mask,50)],[52,48])

    def test_no_count_or_identity_override_and_width_conservation(self):
        mask=np.ones((70,150),dtype=np.uint8)*255
        mask[:10,49]=0;mask[:10,101]=0
        boxes=_split_joined_component((10,0,150,70),np.pad(mask,((0,0),(10,0))),50)
        self.assertEqual(sum(b[2] for b in boxes),150)
        self.assertEqual(boxes[0][0],10)
        self.assertEqual(boxes[-1][0]+boxes[-1][2],160)
