from __future__ import annotations

import unittest

from workspace.vision.audit_independent_meld_crop_coverage import rectangle_coverage


class ReviewedRectangleCoverageTests(unittest.TestCase):
    def test_full_partial_and_disjoint(self) -> None:
        target = (10, 10, 30, 30)
        self.assertEqual(rectangle_coverage((0, 0, 40, 40), target), 1.0)
        self.assertEqual(rectangle_coverage((20, 10, 40, 30), target), 0.5)
        self.assertEqual(rectangle_coverage((30, 10, 40, 30), target), 0.0)

    def test_translation_invariance(self) -> None:
        self.assertEqual(
            rectangle_coverage((12, 14, 25, 29), (10, 10, 30, 30)),
            rectangle_coverage((112, 214, 125, 229), (110, 210, 130, 230)),
        )
