from __future__ import annotations

import unittest

from .geometry_holdout_metrics import _match


class BlindHoldoutMetricTests(unittest.TestCase):
    def test_matches_geometry_once_without_using_region(self) -> None:
        expected = [
            {"pixel_bbox": [10, 10, 20, 30], "region_candidate": "hand"},
            {"pixel_bbox": [40, 10, 20, 30], "region_candidate": "meld"},
        ]
        predicted = [
            {"pixel_bbox": [10, 10, 20, 30], "region_candidate": "hand"},
            {"pixel_bbox": [40, 10, 20, 30], "region_candidate": "hand"},
        ]
        matches = _match(expected, predicted)
        self.assertEqual([candidate["region_candidate"] if candidate else None for _, candidate, _ in matches], ["hand", "hand"])
        self.assertTrue(all(score >= 0.5 for _, _, score in matches))


if __name__ == "__main__":
    unittest.main()
