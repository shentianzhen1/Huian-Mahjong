from __future__ import annotations

import unittest

from workspace.vision.public_meld_private_recovery_source_check import (
    BLOCKED_SOURCE_SHA_MISMATCH,
    SOURCE_SHA_VERIFIED,
    load_recovery_source_checks,
)


PATH = (
    "references/vision/2026-10-01/"
    "public_meld_private_recovery_source_check_v0_1.json"
)


class PublicMeldPrivateRecoverySourceCheckTests(unittest.TestCase):
    def test_repository_source_checks_preserve_fail_closed_boundary(self):
        checks = load_recovery_source_checks(PATH)
        self.assertEqual(
            checks["G09_hand6_p789"].status,
            SOURCE_SHA_VERIFIED,
        )
        self.assertEqual(
            checks["G09_hand6_p789"].expected_source_sha256,
            checks["G09_hand6_p789"].observed_source_sha256,
        )
        self.assertEqual(
            checks["G04_hand3_m456"].status,
            BLOCKED_SOURCE_SHA_MISMATCH,
        )
        self.assertNotEqual(
            checks["G04_hand3_m456"].expected_source_sha256,
            checks["G04_hand3_m456"].observed_source_sha256,
        )


if __name__ == "__main__":
    unittest.main()
