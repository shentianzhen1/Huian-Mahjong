import unittest

from workspace.vision.tiles_runtime_v0_2.whole_hand_baseline_export import (
    _align_exact_counts,
    _sample_summary,
)
from workspace.vision.tiles_runtime_v0_2.whole_hand_eval import (
    FROZEN_CONFIDENCE_THRESHOLD,
)


def _component(x, region, candidate, accepted, confidence=0.9):
    return {
        "pixel_bbox": [x, 400, 40, 70],
        "classification_crop_bbox": [x, 400, 40, 70],
        "region_candidate": region,
        "frame": 100,
        "candidate_tile_id": candidate,
        "tile_id": accepted,
        "tile_confidence": confidence,
        "identity_reason": "accepted" if accepted != "UNKNOWN" else "below_confidence_threshold",
        "private_crop_ref": f"{region}-{x}.png",
    }


class WholeHandBaselineExportTests(unittest.TestCase):
    def test_threshold_remains_frozen_at_point_82(self):
        self.assertEqual(FROZEN_CONFIDENCE_THRESHOLD, 0.82)

    def test_exact_counts_align_left_to_right_and_keep_draw_separate(self):
        sample = {
            "truth": {
                "concealed_hand": ["M1", "M2"],
                "draw_visual": "P9",
            }
        }
        components = [
            _component(80, "hand", "M2", "M2"),
            _component(250, "draw_visual", "P9", "P9"),
            _component(20, "hand", "M1", "M1"),
        ]

        alignment = _align_exact_counts(sample, components)

        self.assertEqual(
            alignment["status"],
            "exact_count_left_to_right_alignment_pending_crop_review",
        )
        self.assertEqual(
            [(row["region"], row["truth_tile"]) for row in alignment["slots"]],
            [("hand", "M1"), ("hand", "M2"), ("draw_visual", "P9")],
        )
        self.assertTrue(all(row["crop_status"] == "unreviewed" for row in alignment["slots"]))

    def test_count_mismatch_never_shifts_truth_into_fake_classifier_errors(self):
        sample = {
            "truth": {
                "concealed_hand": ["M1", "M2", "M3"],
                "draw_visual": None,
            }
        }
        components = [
            _component(20, "hand", "M1", "M1"),
            _component(80, "hand", "M3", "M3"),
        ]

        alignment = _align_exact_counts(sample, components)

        self.assertEqual(alignment["status"], "manual_alignment_required")
        self.assertEqual(alignment["truth_hand_count"], 3)
        self.assertEqual(alignment["detected_hand_count"], 2)
        self.assertEqual(alignment["slots"], [])

    def test_pre_review_summary_keeps_rejection_distinct_from_wrong_accept(self):
        alignment = {
            "status": "exact_count_left_to_right_alignment_pending_crop_review",
            "slots": [
                {"truth_tile": "M1", "accepted_tile_id": "M1"},
                {"truth_tile": "M2", "accepted_tile_id": "M3"},
                {"truth_tile": "M4", "accepted_tile_id": "UNKNOWN"},
            ],
        }
        summary = _sample_summary(alignment, {"geometry_untrusted": False})

        self.assertEqual(summary["accepted_exact_before_crop_review"], 1)
        self.assertEqual(summary["accepted_wrong_before_crop_review"], 1)
        self.assertEqual(summary["rejected_before_crop_review"], 1)
        self.assertTrue(summary["crop_review_required"])


if __name__ == "__main__":
    unittest.main()
