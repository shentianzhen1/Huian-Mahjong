from __future__ import annotations

import unittest

from workspace.vision.public_meld_recovery_projection import (
    project_public_meld_recovery_coverage,
)


class PublicMeldRecoveryProjectionTests(unittest.TestCase):
    def test_projection_separates_all_queued_from_source_verified(self):
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
            source_check_path=(
                "references/vision/2026-10-01/"
                "public_meld_private_recovery_source_check_v0_1.json"
            ),
        )
        self.assertEqual(
            report["all_queued_newly_new_match_query_supported_classes"],
            ["M4", "M5", "M6", "P7", "P8"],
        )
        self.assertEqual(
            report["source_verified_newly_new_match_query_supported_classes"],
            ["P7", "P8"],
        )
        self.assertEqual(
            report["all_queued_newly_introduced_classes"],
            ["P9"],
        )
        self.assertEqual(
            report["source_verified_newly_introduced_classes"],
            ["P9"],
        )
        self.assertEqual(
            report["source_verified_recovery_ids"],
            ["G09_hand6_p789"],
        )
        self.assertEqual(
            report["blocked_recovery_ids"],
            ["G04_hand3_m456"],
        )

        rows = {row["tile_id"]: row for row in report["classes"]}
        for tile in ("P7", "P8"):
            with self.subTest(tile=tile):
                self.assertEqual(
                    rows[tile]["before_independent_match_group_count"], 1
                )
                self.assertEqual(
                    rows[tile][
                        "source_verified_projected_independent_match_group_count"
                    ],
                    2,
                )
                self.assertTrue(
                    rows[tile][
                        "source_verified_projected_new_match_query_support"
                    ]
                )
        for tile in ("M4", "M5", "M6"):
            with self.subTest(tile=tile):
                self.assertEqual(
                    rows[tile][
                        "source_verified_projected_independent_match_group_count"
                    ],
                    1,
                )
                self.assertFalse(
                    rows[tile][
                        "source_verified_projected_new_match_query_support"
                    ]
                )

        self.assertEqual(
            rows["P9"]["source_verified_projected_independent_match_group_count"],
            1,
        )
        self.assertFalse(
            rows["P9"]["source_verified_projected_new_match_query_support"]
        )
        self.assertTrue(
            report["source_verified_projection_is_not_template_eligibility"]
        )
        self.assertFalse(report["formal_promotion_evidence"])
        self.assertFalse(report["safe_for_executor"])


if __name__ == "__main__":
    unittest.main()
