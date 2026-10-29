import unittest
from workspace.vision.tiles_runtime_v0_2.local_dark_meld_probe import (
    complete_gap_groups, propose_local_meld_components,
)


def component(box, role='meld'):
    return dict(pixel_bbox=box, region_candidate=role, frame=1800, session='dev')


class LocalDarkMeldProbeTests(unittest.TestCase):
    def setUp(self):
        self.base = [component(b) for b in [(101,442,51,54), (145,442,49,54),
                                           (248,442,48,54), (294,442,45,54)]]
        self.hand = component((416,442,49,65), 'hand')
        self.base.append(self.hand)
        self.extra = [component(b, 'unknown') for b in [(194,442,42,56), (337,442,44,52)]]

    def test_reviewed_six_face_geometry_preserves_hand_and_original_objects(self):
        result = propose_local_meld_components(self.base, self.extra)
        self.assertEqual([len(g) for g in complete_gap_groups(
            [x for x in result if x['region_candidate']=='meld'])], [3,3])
        for old, new in zip(self.base, result):
            self.assertIs(old, new)
        self.assertEqual(len(self.base), 5)
        self.assertEqual(result[-1]['frame'], 1800)

    def test_partial_recovery_retains_baseline(self):
        self.assertIs(propose_local_meld_components(self.base, self.extra[:1]), self.base)

    def test_duplicate_proposals_do_not_inflate_group(self):
        result = propose_local_meld_components(self.base, self.extra * 2)
        self.assertEqual(len(result), 7)

    def test_far_or_hand_overlapping_faces_are_not_added(self):
        extras = [component((600,442,44,54)), self.hand]
        self.assertIs(propose_local_meld_components(self.base, extras), self.base)
        hand_only = [self.hand]
        self.assertIs(propose_local_meld_components(hand_only, self.extra), hand_only)

    def test_incomplete_groups_request_baseline_fallback(self):
        self.assertIsNone(complete_gap_groups([]))
        self.assertIsNone(complete_gap_groups(self.extra))
