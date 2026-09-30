from __future__ import annotations

import unittest

from workspace.vision.public_meld_private_recovery_queue import (
    load_private_recovery_queue,
    qualify_recovered_item,
)


PATH = "references/vision/2026-10-01/public_meld_private_recovery_queue_v0_1.json"


class PublicMeldPrivateRecoveryQueueTests(unittest.TestCase):
    def test_repository_queue_locks_two_high_value_groups_to_one_match(self):
        queue = load_private_recovery_queue(PATH)
        self.assertEqual(queue.match_group, "reviewed_match_2026_09_19_eight_hand")
        self.assertEqual(len(queue.items), 2)
        self.assertEqual(queue.items[0].expected_tiles, ("M4", "M5", "M6"))
        self.assertEqual(queue.items[1].expected_tiles, ("P7", "P8", "P9"))
        self.assertTrue(queue.same_match_chunks_are_not_independent)
        self.assertTrue(all(not item.holdout_eligible for item in queue.items))

    def test_recovery_requires_exact_source_and_review_lineage(self):
        queue = load_private_recovery_queue(PATH)
        item = queue.items[0]
        self.assertTrue(
            qualify_recovered_item(
                item,
                actual_source_sha256=item.source_sha256_from_repository_evidence,
                pixel_crop_matches_review_packet=True,
                frame_lineage_verified=True,
            )
        )
        self.assertFalse(
            qualify_recovered_item(
                item,
                actual_source_sha256="0" * 64,
                pixel_crop_matches_review_packet=True,
                frame_lineage_verified=True,
            )
        )
        self.assertFalse(
            qualify_recovered_item(
                item,
                actual_source_sha256=item.source_sha256_from_repository_evidence,
                pixel_crop_matches_review_packet=False,
                frame_lineage_verified=True,
            )
        )
        self.assertFalse(
            qualify_recovered_item(
                item,
                actual_source_sha256=item.source_sha256_from_repository_evidence,
                pixel_crop_matches_review_packet=True,
                frame_lineage_verified=False,
            )
        )


if __name__ == "__main__":
    unittest.main()
