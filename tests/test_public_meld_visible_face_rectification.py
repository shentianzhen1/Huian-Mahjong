import importlib.util
import unittest

VISION = all(importlib.util.find_spec(n) for n in ("PIL", "numpy", "cv2"))


@unittest.skipUnless(VISION, "optional Vision dependencies required")
class VisibleFaceRectificationTests(unittest.TestCase):
    def test_identity_rectangle_preserves_source_artwork(self):
        import numpy as np
        from PIL import Image
        from workspace.vision.public_meld_visible_face_rectification import rectify_reviewed_visible_face
        pixels = np.arange(20*30*3, dtype=np.uint8).reshape(30,20,3)
        out = rectify_reviewed_visible_face(Image.fromarray(pixels), ((0,0),(19,0),(19,29),(0,29)), output_size=(20,30))
        np.testing.assert_array_equal(np.array(out), pixels)

    def test_invalid_geometry_does_not_fill_or_clip_missing_pixels(self):
        from PIL import Image
        from workspace.vision.public_meld_visible_face_rectification import rectify_reviewed_visible_face
        image = Image.new("RGB", (50,80))
        for corners in (((-1,0),(40,0),(40,60),(0,60)),
                        ((0,0),(40,60),(40,0),(0,60)),
                        ((0,0),(40,0),(40,0),(0,60)),
                        ((0,0),(float("nan"),0),(40,60),(0,60))):
            with self.assertRaises(ValueError):
                rectify_reviewed_visible_face(image, corners, output_size=(40,60))
