from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

VISION = all(
    importlib.util.find_spec(name) is not None
    for name in ("PIL", "cv2", "numpy")
)

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(VISION, "Pillow/OpenCV/numpy are optional in core-only installs")
class PublicMeldConcealedTransferEvaluationTests(unittest.TestCase):
    def test_normalized_public_meld_transfer_is_diagnostic_only(self):
        from workspace.vision.tiles_runtime_v0_2.evaluate_public_meld_concealed_transfer import (
            evaluate_public_meld_concealed_transfer,
        )

        report = evaluate_public_meld_concealed_transfer(ROOT)
        self.assertEqual(report["target_group_count"], 7)
        self.assertEqual(report["target_face_count"], 21)
        self.assertLessEqual(report["prepared_group_count"], 7)
        self.assertLessEqual(report["scored_face_count"], 21)
        self.assertFalse(report["changes_runtime_behavior"])
        self.assertFalse(report["formal_promotion_evidence"])
        self.assertFalse(report["safe_for_hint"])
        self.assertFalse(report["safe_for_executor"])

        # Temporary concise CI diagnostic for the A/B decision. Keep values
        # visible without dumping source paths or per-face data.
        print(
            "PUBLIC_MELD_CONCEALED_TRANSFER="
            + json.dumps(
                {
                    "prepared_groups": report["prepared_group_count"],
                    "scored_faces": report["scored_face_count"],
                    "raw_exact_accuracy": report["raw_exact_accuracy"],
                    "accepted_count": report["runtime_gate_accepted_count"],
                    "accepted_accuracy": report["runtime_gate_accepted_accuracy"],
                    "exact_session_exclusion_effective": report[
                        "exact_session_exclusion_effective"
                    ],
                },
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    unittest.main()
