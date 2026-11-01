import json
from pathlib import Path
import unittest

from workspace.vision.opponent_meld_template_coverage import run


ROOT = Path(__file__).resolve().parents[1]
FROZEN = (
    ROOT
    / "references/vision/2026-10-01/"
    "opponent_meld_s456_template_coverage_v0_1.json"
)


class OpponentMeldTemplateCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generated = run(ROOT)
        cls.frozen = json.loads(FROZEN.read_text(encoding="utf-8"))

    def test_s456_query_match_is_excluded(self):
        self.assertEqual(
            self.generated["query_match_group_excluded"],
            "reviewed_match_2026_09_26_first_hand",
        )
        for row in self.generated["per_tile"].values():
            self.assertNotIn(
                "reviewed_match_2026_09_26_first_hand",
                row["labels_by_match_group"],
            )

    def test_independence_is_counted_by_original_match_group(self):
        expected = {
            "S4": (2, 2),
            "S5": (1, 1),
            "S6": (1, 1),
        }
        for tile, (labels, groups) in expected.items():
            row = self.generated["per_tile"][tile]
            self.assertEqual(row["qualified_label_count"], labels)
            self.assertEqual(row["independent_match_group_count"], groups)
            self.assertEqual(
                len(row["labels_by_match_group"]),
                groups,
            )

    def test_current_gate_remains_data_coverage_thin(self):
        self.assertEqual(
            self.generated["minimum_independent_match_groups_across_targets"],
            1,
        )
        self.assertEqual(
            self.generated["interpretation_gate"],
            "DATA_COVERAGE_THIN",
        )
        self.assertFalse(self.generated["safe_for_runtime"])
        self.assertFalse(self.generated["safe_for_hint"])
        self.assertFalse(self.generated["safe_for_executor"])

    def test_frozen_measurement_matches_current_counts(self):
        for tile in ("S4", "S5", "S6"):
            generated = self.generated["per_tile"][tile]
            frozen = self.frozen["per_tile"][tile]
            self.assertEqual(
                generated["qualified_label_count"],
                frozen["qualified_label_count"],
            )
            self.assertEqual(
                generated["independent_match_group_count"],
                frozen["independent_match_group_count"],
            )
            self.assertEqual(
                generated["labels_by_match_group"],
                frozen["labels_by_match_group"],
            )


if __name__ == "__main__":
    unittest.main()
