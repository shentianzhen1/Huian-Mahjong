import unittest
from dataclasses import replace

try:
    from workspace.vision.tiles_runtime_v0_2.dynamic_geometry import (
        GeometryComponent, GeometryFrame, fuse_dynamic_geometry, select_identity_geometry)
except ImportError:
    GeometryFrame = None


@unittest.skipUnless(GeometryFrame is not None, 'Vision dependencies unavailable')
class BurstIdentityGeometryTests(unittest.TestCase):
    def frame(self, n, count=3, bad=False, session='test'):
        components = tuple(GeometryComponent((i*50, 400, 49, 70), (.1,.8,.04,.1),
            'hand', .92, n, session) for i in range(count))
        return GeometryFrame(components, bad, (), n, session)

    def test_earlier_identity_uses_its_own_geometry_keeps_three_votes(self):
        frames = [self.frame(n) for n in [72,78,84]]
        fused = fuse_dynamic_geometry(frames)
        selected = select_identity_geometry(fused, frames, 78)
        self.assertEqual(selected.frame, 78)
        self.assertTrue(all(c.frame == 78 for c in selected.components))
        self.assertEqual(selected.issues, ('stable_votes=3',))
        self.assertEqual(fused.frame, 84)

    def test_missing_repeated_conflicted_and_cross_session_frames_rejected(self):
        frames = [self.frame(n) for n in [72,78,84]]
        fused = fuse_dynamic_geometry(frames)
        for candidates, wanted in [(frames,90), ([frames[0],frames[0],frames[2]],72),
                ([frames[0],self.frame(78,count=4),frames[2]],78),
                ([frames[0],self.frame(78,bad=True),frames[2]],78),
                ([frames[0],self.frame(78,session='other'),frames[2]],78)]:
            with self.subTest(wanted=wanted):
                with self.assertRaises(ValueError):
                    select_identity_geometry(fused,candidates,wanted)

    def test_selection_cannot_rescue_unstable_burst(self):
        frames = [self.frame(72),self.frame(78,count=4),self.frame(84)]
        fused = fuse_dynamic_geometry(frames)
        self.assertTrue(fused.geometry_untrusted)
        self.assertIs(select_identity_geometry(fused,frames,78),fused)
