import unittest

from workspace.vision.concealed_template_lineage_recovery import (
    build_concealed_identity_lineage_recovery_queue,
)


class ConcealedTemplateLineageRecoveryDomainTests(unittest.TestCase):
    def test_draw_visual_participates_in_concealed_identity_lineage(self):
        missing_sha = "a" * 64
        labels = [
            {
                "tile_id": "P2",
                "region": "draw_visual",
                "approved": True,
                "gold_skin_only": False,
                "sha256": missing_sha,
                "source_session": "session-a",
                "source_frame": 60,
            },
            {
                "tile_id": "SOUTH",
                "region": "hand_region",
                "approved": True,
                "gold_skin_only": False,
                "sha256": missing_sha,
                "source_session": "session-a",
                "source_frame": 180,
            },
            {
                "tile_id": "P9",
                "region": "draw_visual",
                "approved": True,
                "gold_skin_only": True,
                "sha256": missing_sha,
                "source_session": "session-a",
                "source_frame": 60,
            },
        ]

        report = build_concealed_identity_lineage_recovery_queue(
            labels,
            {},
            target_classes={"P2", "SOUTH", "P9"},
        )

        self.assertEqual(report["unresolved_source_count"], 1)
        self.assertEqual(report["unresolved_label_count"], 2)
        self.assertEqual(report["items"][0]["tile_classes"], ["P2", "SOUTH"])
        self.assertEqual(report["items"][0]["source_frames"], [60, 180])

    def test_legacy_builder_remains_hand_only_for_frozen_artifacts(self):
        from workspace.vision.concealed_template_lineage_recovery import (
            build_lineage_recovery_queue,
        )

        labels = [
            {
                "tile_id": "P2",
                "region": "draw_visual",
                "approved": True,
                "sha256": "b" * 64,
            }
        ]
        report = build_lineage_recovery_queue(labels, {}, target_classes={"P2"})
        self.assertEqual(report["items"], [])


if __name__ == "__main__":
    unittest.main()
