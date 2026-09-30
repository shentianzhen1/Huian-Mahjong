from __future__ import annotations

import unittest

from workspace.vision.public_meld_recovery_projection import (
    project_public_meld_recovery_coverage,
)


class PublicMeldRecoveryProjectionTests(unittest.TestCase):
    def test_high_value_recovery_has_expected_independent_match_impact(self):
        report = project_public_meld_recovery_coverage(
            manifest_path=(
                "references/vision/2026-09-22/"
                "public_identity_labels_v0_1.json"
            ),
            registry_path=(
                "references/vision/2026-09-24/"
                "public_identity_source_groups.development.json"
            ),
            recovery_queue_path=(
                "references/vision/2026-10-01/"
                "public_meld_private_recovery_queue_v0_1.json"
            ),
        )
        self.assertEqual(
            report["newly_new_match_query_supported_classes"],
            ["M4", "M5", "M6", "P7", "P8"],
        )
        self.assertEqual(
            report["newly_introduced_classes"],
            ["P9"],
        )
        rows = {row["tile_id"]: row for row in report["classes"]}
        for tile in ("M4", "M5", "M6", "P7", "P8"):
            with self.subTest(tile=tile):
                self.assertEqual(
                    rows[tile]["before_independent_match_group_count"], 1
                )
                self.assertEqual(
                    rows[tile]["projected_independent_match_group_count"], 2
                )
                self.assertTrue(
                    rows[tile]["projected_new_match_query_support"]
                )
        self.assertEqual(rows["P9"]["before_independent_match_group_count"], 0)
        self.assertEqual(rows["P9"]["projected_independent_match_group_count"], 1)
        self.assertFalse(rows["P9"]["projected_new_match_query_support"])
        self.assertFalse(report["formal_promotion_evidence"])
        self.assertFalse(report["safe_for_executor"])


if __name__ == "__main__":
    unittest.main()
