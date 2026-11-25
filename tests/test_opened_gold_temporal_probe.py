import unittest
from workspace.vision.tiles_runtime_v0_2.opened_gold_temporal_probe import shadow_windows


class GoldTemporalShadowTests(unittest.TestCase):
    def setUp(self):
        self.observations = [dict(frame=i, candidate='M4', full_frame_rgb_sha256=str(i))
                             for i in (0,6,12)]
        self.rows = [dict(frames=[0,6,12], pixel_sha256=['0','6','12'],
                         geometry_untrusted=True, display_allowed=False)]

    def test_agreement_does_not_open_advice_or_clear_bad_hand_geometry(self):
        row = shadow_windows(self.observations, self.rows)[0]
        self.assertTrue(row['candidate_agreement'])
        self.assertTrue(row['whole_geometry_untrusted'])
        self.assertFalse(row['baseline_advice_allowed'])

    def test_missing_or_unknown_frame_does_not_carry_previous_gold(self):
        for unknown in (None, 'UNKNOWN'):
            with self.subTest(unknown=unknown):
                self.observations[-1]['candidate'] = unknown
                row = shadow_windows(self.observations, self.rows)[0]
                self.assertFalse(row['candidate_agreement'])
                self.assertIsNone(row['candidate'])

    def test_conflicting_identity_is_not_a_stable_window(self):
        self.observations[-1]['candidate'] = 'M6'
        self.assertFalse(shadow_windows(self.observations, self.rows)[0]['candidate_agreement'])

    def test_stale_rgb_hash_is_rejected(self):
        self.observations[-1]['full_frame_rgb_sha256'] = 'other-frame'
        with self.assertRaises(ValueError):
            shadow_windows(self.observations, self.rows)

    def test_repeated_capture_cannot_count_as_three_observations(self):
        self.rows[0].update(frames=[0,0,0], pixel_sha256=['0','0','0'])
        with self.assertRaises(ValueError):
            shadow_windows(self.observations, self.rows)
