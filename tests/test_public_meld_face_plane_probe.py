"""Geometry checks do not assert tile identity."""
import importlib.util
import unittest


@unittest.skipUnless(all(importlib.util.find_spec(n) for n in ('PIL', 'cv2', 'numpy')), 'optional vision dependencies')
class FacePlaneTests(unittest.TestCase):
    def image(self, dx=0, dy=0, seams=True):
        from PIL import Image, ImageDraw
        image = Image.new('RGB', (260, 190), (3, 65, 76))
        draw = ImageDraw.Draw(image)
        draw.rectangle((45+dx, 55+dy, 174+dx, 119+dy), fill=(30, 110, 80))
        draw.rectangle((45+dx, 55+dy, 174+dx, 109+dy), fill=(225, 230, 220))
        if seams:
            for x in (90, 132):
                draw.line((x+dx, 55+dy, x-5+dx, 109+dy), fill=(50, 50, 50), width=2)
        return image

    def test_sloping_seams_and_translation(self):
        from workspace.vision.public_meld_outer_body_probe import face_plane_quads
        quads, audit = face_plane_quads(self.image(), (40, 45, 140, 80))
        moved, _ = face_plane_quads(self.image(9, 7), (49, 52, 140, 80))
        self.assertEqual(len(quads), 3)
        self.assertGreater(quads[0][1][0], quads[0][2][0])
        for a, b in zip(quads, moved):
            for (x, y), (mx, my) in zip(a, b):
                self.assertAlmostEqual(mx, x+9)
                self.assertAlmostEqual(my, y+7)
        self.assertLess(audit['face_plane_rows'][1], audit['outer_body_xyxy'][3])

    def test_missing_seams_abstain(self):
        from workspace.vision.public_meld_outer_body_probe import face_plane_quads
        quads, audit = face_plane_quads(self.image(seams=False), (40, 45, 140, 80))
        self.assertEqual(quads, ())
        self.assertEqual(audit['reason'], 'seam_absent_or_search_edge')

    def test_rectification_outputs_three_images(self):
        from workspace.vision.public_meld_outer_body_probe import face_plane_quads, rectify_face_quad
        image = self.image()
        quads, _ = face_plane_quads(image, (40, 45, 140, 80))
        self.assertTrue(all(rectify_face_quad(image, q).width > 30 for q in quads))
