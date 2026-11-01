"""Check experimental geometry abstention and coordinate invariance."""
import importlib.util
import unittest
VISION = all(importlib.util.find_spec(n) for n in ('PIL','cv2','numpy'))

@unittest.skipUnless(VISION, 'optional vision dependencies')
class BodyContextTests(unittest.TestCase):
    def image(self, dx=0, dy=0, stacked=False):
        from PIL import Image, ImageDraw
        im=Image.new('RGB',(300,220),(0,75,78));d=ImageDraw.Draw(im)
        y=70 if stacked else 40
        for x in (25,85,145):
            d.rectangle((x+dx,y+dy,x+54+dx,y+85+dy),fill=(235,235,225))
        if stacked:
            d.rectangle((85+dx,15+dy,139+dx,100+dy),fill=(235,235,225))
        return im
    def candidate(self, bbox):
        from workspace.vision.public_tile_detector import PublicGeometryCandidate
        return PublicGeometryCandidate(bbox,(0,0,1,1),'bottom_group',.9,.8,None,None)
    def test_translation_moves_all_crop_edges_equally(self):
        from workspace.vision.evaluate_sift_detector_body_boundary_probe import raw_face_boxes
        a,_=raw_face_boxes(self.image(),self.candidate((20,30,185,105)),body_context=True)
        b,_=raw_face_boxes(self.image(11,17),self.candidate((31,47,185,105)),body_context=True)
        self.assertEqual(len(a),3)
        self.assertEqual(b,tuple((x+11,y+17,r+11,t+17) for x,y,r,t in a))
        self.assertTrue(all(a[i][2] > a[i+1][0] for i in range(2)))
    def test_stacked_never_enters_flat_splitter(self):
        from workspace.vision.evaluate_sift_detector_body_boundary_probe import raw_face_boxes
        boxes,_=raw_face_boxes(self.image(stacked=True),self.candidate((20,10,185,150)),body_context=True)
        self.assertEqual(boxes,())
    def test_negative_context_is_rejected(self):
        from workspace.vision.evaluate_sift_detector_body_boundary_probe import raw_face_boxes
        with self.assertRaises(ValueError):
            raw_face_boxes(self.image(),self.candidate((20,30,185,105)),seam_context=-1)
