from __future__ import annotations

import unittest

from workspace.vision.public_meld_private_recovery_result import (
    BLOCKED,
    BlockedPrivateRecovery,
    RecoveredPrivateTemplate,
    load_private_recovery_results,
)


PATH = (
    "references/vision/2026-10-01/"
    "public_meld_private_recovery_result_v0_1.json"
)


class PublicMeldPrivateRecoveryResultTests(unittest.TestCase):
    def test_g09_is_recovered_and_g04_remains_blocked(self):
        results = load_private_recovery_results(PATH)

        g09 = results["G09_hand6_p789"]
        self.assertIsInstance(g09, RecoveredPrivateTemplate)
        self.assertEqual(g09.tile_ids, ("P7", "P8", "P9"))
        self.assertTrue(g09.private_template_eligible)
        self.assertEqual(
            g09.source_sha256,
            "d50f6722982adb0fdfe3ad8e0b9d1f4155defcfbefebd77e8f10cbc4d3b19a78",
        )
        self.assertEqual(g09.frame_index, 1740)
        self.assertEqual(
            g09.private_label_manifest_sha256,
            "9d89e9cf2f7859a2a24bebce91632e854299df2404c92f0fdf9a96e3a2884427",
        )

        g04 = results["G04_hand3_m456"]
        self.assertIsInstance(g04, BlockedPrivateRecovery)
        self.assertEqual(g04.status, BLOCKED)
        self.assertFalse(g04.private_template_eligible)


if __name__ == "__main__":
    unittest.main()
