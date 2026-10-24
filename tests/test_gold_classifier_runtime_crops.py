import tempfile
from pathlib import Path
import unittest

try:
    from PIL import Image
    import numpy as np
    from workspace.vision.tiles_v0_1.gold_classifier import _crop_label
except ImportError:
    Image = np = None


@unittest.skipUnless(Image is not None and np is not None, 'Vision dependencies unavailable')
class GoldClassifierRuntimeCropTests(unittest.TestCase):
    def test_tile_only_template_uses_pixels_not_original_frame_bbox(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'templates/hand').mkdir(parents=True)
            original = Image.new('RGB', (40, 69), 'white')
            original.putpixel((20, 30), (0, 120, 20))
            original.save(root/'templates/hand/tile.png')
            crop = _crop_label(root, dict(image='templates/hand/tile.png', bbox=[448,409,40,69]))
            self.assertEqual(crop.size, original.size)
            self.assertTrue(np.array_equal(np.asarray(crop), np.asarray(original)))

    def test_full_frame_source_still_uses_its_bbox(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original = Image.new('RGB', (100, 100), 'black')
            original.paste((255, 255, 255), (20, 30, 60, 90))
            original.save(root/'frame.png')
            crop = _crop_label(root, dict(image='frame.png', bbox=[20,30,40,60]))
            self.assertEqual(crop.size, (40, 60))
            self.assertEqual(crop.getpixel((0,0)), (255,255,255))

    def test_pip_diagnostic_cannot_replace_seven_with_five(self):
        from unittest.mock import patch
        from workspace.vision.tiles_v0_1.gold_classifier import GoldTileClassifier
        classifier = GoldTileClassifier({'P7': [np.ones((2,128), np.float32)]})
        with patch.object(classifier, '_rank', return_value=[('P7',20),('P6',18)]), \
                patch('workspace.vision.tiles_v0_1.gold_classifier.count_tong_pips', return_value=5):
            result = classifier.classify(Image.new('RGB', (42,57)))
        self.assertEqual(result.tile_id, 'P7')
        self.assertEqual(result.pip_count, 5)

    def test_wan_numeral_beats_shared_lower_glyph(self):
        from unittest.mock import patch
        from workspace.vision.tiles_v0_1.gold_classifier import GoldTileClassifier
        descriptors = {'M1':[np.ones((2,128), np.float32)], 'M3':[np.ones((2,128), np.float32)]}
        classifier = GoldTileClassifier(descriptors, descriptors)
        with patch.object(classifier, '_rank', return_value=[('M3',36),('M1',35)]), \
                patch.object(classifier, '_rank_numerals', return_value=[('M1',4),('M3',2)]):
            result = classifier.classify(Image.new('RGB', (42,57)))
        self.assertEqual(result.tile_id, 'M1')
        self.assertEqual(result.method, 'sift_wan_numeral')
        self.assertEqual(result.evidence_count, 4)

    def test_tied_numerals_preserve_full_face_result(self):
        from unittest.mock import patch
        from workspace.vision.tiles_v0_1.gold_classifier import GoldTileClassifier
        descriptors = {'M1':[np.ones((2,128), np.float32)], 'M3':[np.ones((2,128), np.float32)]}
        classifier = GoldTileClassifier(descriptors, descriptors)
        with patch.object(classifier, '_rank', return_value=[('M3',36),('M1',35)]), \
                patch.object(classifier, '_rank_numerals', return_value=[('M1',2),('M3',2)]):
            self.assertEqual(classifier.classify(Image.new('RGB', (42,57))).tile_id, 'M3')
