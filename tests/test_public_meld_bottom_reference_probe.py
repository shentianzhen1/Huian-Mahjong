import importlib.util
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(all(importlib.util.find_spec(n) for n in ('cv2', 'numpy', 'PIL')), 'optional vision dependencies')
class BottomReferenceIntegrityTests(unittest.TestCase):
    def test_similarly_named_wrong_source_is_rejected_before_decode(self):
        from workspace.vision.public_meld_bottom_reference_probe import load_bottom_s234_templates
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'ScreenRecording_09-26-2026_22-30-33_1.mp4'
            source.write_bytes(b'unrelated-video-bytes')
            with self.assertRaisesRegex(ValueError, 'source SHA mismatch'):
                load_bottom_s234_templates(source)
