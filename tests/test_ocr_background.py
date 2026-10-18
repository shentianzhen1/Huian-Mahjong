"""OCR helpers must not create a new console for every frame on Windows."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

try:
    import numpy as np
    from workspace.vision.tiles_v0_1.public_state_scores import TesseractCLIBackend
except ImportError:
    TesseractCLIBackend = None


@unittest.skipIf(TesseractCLIBackend is None, 'optional Vision dependencies unavailable')
class BackgroundOCRTests(unittest.TestCase):
    def test_windows_hides_console_and_preserves_ocr_output_and_timeout(self):
        backend = TesseractCLIBackend(timeout_seconds=2.5)
        with patch.object(backend, 'available', return_value=True), \
             patch('workspace.vision.tiles_v0_1.public_state_scores.sys.platform', 'win32'), \
             patch('workspace.vision.tiles_v0_1.public_state_scores.subprocess.CREATE_NO_WINDOW', 0x08000000, create=True), \
             patch('workspace.vision.tiles_v0_1.public_state_scores.subprocess.run',
                   return_value=SimpleNamespace(returncode=0, stdout=b'1000\n', stderr=b'')) as run:
            self.assertEqual(backend(np.ones((20, 60), dtype=np.uint8)), '1000')
        self.assertEqual(run.call_args.kwargs['creationflags'], 0x08000000)
        self.assertEqual(run.call_args.kwargs['timeout'], 2.5)
        self.assertTrue(run.call_args.kwargs['input'])
