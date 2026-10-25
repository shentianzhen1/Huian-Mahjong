import unittest

import numpy as np

from workspace.vision.tiles_runtime_v0_2.dynamic_geometry import _meld_like_group


class MovingDrawGeometryTests(unittest.TestCase):
    def test_isolated_short_face_is_not_meld_evidence(self):
        mask = np.zeros((512, 1108), dtype=np.uint8)
        hand = [(117 + 50 * i, 439, 49, 69) for i in range(16)]
        # Reviewed frame 1218: nine-wan is leaving the draw position.
        self.assertFalse(_meld_like_group([(943, 425, 47, 54)], hand, mask, 49))

    def test_separated_multi_face_meld_remains_candidate(self):
        mask = np.zeros((512, 1108), dtype=np.uint8)
        hand = [(267 + 50 * i, 439, 49, 69) for i in range(13)]
        group = [(101, 416, 45, 80), (146, 416, 45, 80), (188, 418, 48, 78)]
        self.assertTrue(_meld_like_group(group, hand, mask, 49))
