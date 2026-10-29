import unittest
from unittest.mock import Mock
try:
    from PIL import Image
    from workspace.vision.tiles_v0_1.public_state_status import TesseractStatusReader
except ImportError:
    Image = None


@unittest.skipUnless(Image is not None, 'Vision dependencies unavailable')
class HandProgressCropFallbackTests(unittest.TestCase):
    def test_valid_primary_is_preserved_without_extra_ocr(self):
        backend = Mock(side_effect=['92', '2/8'])
        read = TesseractStatusReader(backend).read(Image.new('RGB', (1108, 512)))
        self.assertEqual(read.hand_number, 2)
        self.assertEqual(read.hand_mode, 'primary')
        self.assertIsNone(read.raw_hand_fallback)
        self.assertEqual(backend.call_count, 2)

    def test_invalid_primary_retries_taller_crop_and_retains_raw_evidence(self):
        backend = Mock(side_effect=['92', '2/6', '2/8'])
        read = TesseractStatusReader(backend).read(Image.new('RGB', (1108, 512)))
        self.assertEqual(read.hand_number, 2)
        self.assertEqual(read.raw_hand_progress, '2/6')
        self.assertEqual(read.raw_hand_fallback, '2/8')
        self.assertEqual(read.hand_mode, 'top_expand_fallback')
        primary = backend.call_args_list[1].args[0]
        fallback = backend.call_args_list[2].args[0]
        self.assertGreater(fallback.shape[0], primary.shape[0])
        self.assertEqual(fallback.shape[1], primary.shape[1])

    def test_invalid_denominator_is_never_rewritten(self):
        backend = Mock(side_effect=['92', '2/6', '2/6'])
        read = TesseractStatusReader(backend).read(Image.new('RGB', (1108, 512)))
        self.assertIsNone(read.hand_number)
        self.assertIn('hand_unreadable', read.issues)
        self.assertEqual(read.hand_mode, 'invalid')
