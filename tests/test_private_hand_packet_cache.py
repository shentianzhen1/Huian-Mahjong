import hashlib
import json
from pathlib import Path
import tempfile
import unittest

try:
    from PIL import Image
    import cv2
except ImportError:
    Image = None


@unittest.skipUnless(Image is not None, 'Vision dependencies unavailable')
class PrivateHandPacketCacheTests(unittest.TestCase):
    def test_reuse_session_separation_and_corruption_detection(self):
        from workspace.vision.tiles_runtime_v0_2.experimental_hand_translation import cached_private_hand_packet
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            image = Image.new('RGB', (48, 72), 'white')
            image.save(path / 'tile.png')
            row = {'crop': 'tile.png', 'truth': 'P2',
                   'rgb_sha256': hashlib.sha256(image.tobytes()).hexdigest()}
            manifest = path / 'selected.json'
            manifest.write_text(json.dumps({'rows': [row]}))
            resources = {'classifier': object()}
            first = cached_private_hand_packet(resources, manifest)
            self.assertIs(first['classifier'], cached_private_hand_packet(resources, manifest)['classifier'])
            self.assertIsNot(first['classifier'], cached_private_hand_packet({'classifier': object()}, manifest)['classifier'])
            image.putpixel((20, 20), (0, 0, 0))
            image.save(path / 'tile.png')
            with self.assertRaisesRegex(ValueError, 'RGB mismatch'):
                cached_private_hand_packet(resources, manifest)
            self.assertNotIn('extra_features', resources)
