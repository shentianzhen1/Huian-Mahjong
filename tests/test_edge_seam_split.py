import unittest
try:
 import numpy as np
 from workspace.vision.tiles_runtime_v0_2.dynamic_geometry import _split_joined_component
except ImportError:
 np=None

@unittest.skipIf(np is None,'Vision dependencies unavailable')
class EdgeSeamSplitTests(unittest.TestCase):
 def test_glyph_valley_does_not_move_tile_boundary(self):
  mask=np.full((70,100),255,np.uint8);mask[10:60,39:42]=0
  self.assertEqual(_split_joined_component((0,0,100,70),mask,50,edge_seams=True),[(0,0,50,70),(50,0,50,70)])
  self.assertNotEqual(_split_joined_component((0,0,100,70),mask,50),[(0,0,50,70),(50,0,50,70)])
 def test_real_edge_seam_is_preserved(self):
  mask=np.full((70,100),255,np.uint8);mask[:,53]=0
  self.assertEqual(_split_joined_component((0,0,100,70),mask,50,edge_seams=True),[(0,0,53,70),(53,0,47,70)])
 def test_flat_edges_do_not_bias_towards_search_window_start(self):
  mask=np.full((70,150),255,np.uint8)
  self.assertEqual(_split_joined_component((0,0,150,70),mask,50,edge_seams=True),[(0,0,50,70),(50,0,50,70),(100,0,50,70)])
