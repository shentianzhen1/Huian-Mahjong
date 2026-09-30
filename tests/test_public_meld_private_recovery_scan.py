from __future__ import annotations

import unittest

from workspace.vision.public_meld_private_recovery_scan import (
    RecoveryObservation,
    bbox_iou,
    cluster_recovery_observations,
)


class PublicMeldPrivateRecoveryScanTests(unittest.TestCase):
    def test_iou_and_stable_cluster(self):
        base = (0.10, 0.80, 0.12, 0.12)
        observations = [
            RecoveryObservation(100, 10.00, "bottom_group", base, 0.80),
            RecoveryObservation(103, 10.10, "bottom_group", (0.101, 0.801, 0.12, 0.12), 0.82),
            RecoveryObservation(106, 10.20, "bottom_group", (0.099, 0.799, 0.121, 0.121), 0.81),
            RecoveryObservation(109, 10.30, "single_face", (0.6, 0.4, 0.03, 0.08), 0.9),
        ]
        self.assertGreater(bbox_iou(base, observations[1].normalized_bbox), 0.90)
        clusters = cluster_recovery_observations(observations)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0].observation_count, 3)
        self.assertEqual(clusters[0].geometry_kind, "bottom_group")
        report = clusters[0].to_dict()
        self.assertEqual(report["tile_identity"], "UNKNOWN")
        self.assertFalse(report["formal_promotion_evidence"])
        self.assertFalse(report["safe_for_executor"])

    def test_distinct_melds_are_not_collapsed(self):
        observations = [
            RecoveryObservation(1, 1.0, "bottom_group", (0.10, 0.80, 0.10, 0.10), 0.8),
            RecoveryObservation(2, 1.1, "bottom_group", (0.10, 0.80, 0.10, 0.10), 0.8),
            RecoveryObservation(3, 1.2, "bottom_group", (0.10, 0.80, 0.10, 0.10), 0.8),
            RecoveryObservation(1, 1.0, "bottom_group", (0.30, 0.80, 0.10, 0.10), 0.8),
            RecoveryObservation(2, 1.1, "bottom_group", (0.30, 0.80, 0.10, 0.10), 0.8),
            RecoveryObservation(3, 1.2, "bottom_group", (0.30, 0.80, 0.10, 0.10), 0.8),
        ]
        clusters = cluster_recovery_observations(observations)
        self.assertEqual(len(clusters), 2)

    def test_invalid_geometry_fails_closed(self):
        with self.assertRaises(ValueError):
            bbox_iou((0, 0, 0, 1), (0, 0, 1, 1))
        with self.assertRaises(ValueError):
            cluster_recovery_observations([], minimum_observations=0)
        with self.assertRaises(ValueError):
            cluster_recovery_observations([], minimum_iou=0)


if __name__ == "__main__":
    unittest.main()
