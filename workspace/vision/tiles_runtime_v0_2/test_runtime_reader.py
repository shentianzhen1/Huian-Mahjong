from __future__ import annotations

import unittest

from .runtime_reader import identity_gate


class RuntimeReaderGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.covered = {
            *(f"M{rank}" for rank in range(1, 10)),
            *(f"P{rank}" for rank in range(1, 10)),
            *(f"S{rank}" for rank in range(1, 10)),
            "E", "SOUTH", "W", "N", "R", "G", "B",
        }
        self.cross_session = {"hand_region": {"M3", "P9"}}

    def gate(self, tile_id: str, confidence: float, covered=None):
        return identity_gate(
            tile_id,
            confidence,
            region="hand_region",
            covered_classes=self.covered if covered is None else covered,
            cross_session_classes=self.cross_session,
            confidence_threshold=0.82,
        )

    def test_known_runtime_session_is_excluded_from_templates(self) -> None:
        labels = [
            {"tile_id": "P9", "approved": True, "source_session": "session_a"},
            {"tile_id": "P9", "approved": True, "source_session": "session_b"},
            {"tile_id": "P9", "approved": True, "source_session": "session_c"},
        ]
        filtered = _training_labels(labels, "session_b")
        self.assertEqual([row["source_session"] for row in filtered], ["session_a", "session_c"])

    def test_unknown_runtime_session_keeps_all_templates(self) -> None:
        labels = [{"tile_id": "P9", "approved": True, "source_session": "session_a"}]
        self.assertEqual(_training_labels(labels, None), labels)

    def test_high_confidence_cross_session_class_is_accepted(self) -> None:
        self.assertEqual(self.gate("P9", 0.93), ("P9", "accepted"))

    def test_low_confidence_is_unknown(self) -> None:
        self.assertEqual(
            self.gate("P9", 0.81),
            ("UNKNOWN", "below_confidence_threshold"),
        )

    def test_missing_m2_blocks_wan_identity_instead_of_silent_mislabel(self) -> None:
        covered = set(self.covered)
        covered.remove("M2")
        self.assertEqual(
            self.gate("M3", 0.99, covered),
            ("UNKNOWN", "category_has_missing_standard_class"),
        )

    def test_single_session_class_is_unknown(self) -> None:
        self.assertEqual(
            self.gate("P8", 0.99),
            ("UNKNOWN", "class_not_cross_session_validated_in_region"),
        )


if __name__ == "__main__":
    unittest.main()
