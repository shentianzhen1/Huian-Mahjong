import importlib.util
import unittest


VISION = all(
    importlib.util.find_spec(name) is not None
    for name in ("PIL", "cv2", "numpy")
)


@unittest.skipUnless(
    VISION,
    "Pillow/OpenCV/numpy are optional in core-only installs",
)
class OpponentPublicMeldMobileNetLogicTests(unittest.TestCase):
    def test_unordered_top1_does_not_assume_display_order(self):
        from workspace.vision.opponent_public_meld_mobilenet import (
            _unordered_top1_exact,
        )

        scores = [
            {"M2": 0.9, "M1": 0.2},
            {"M1": 0.8, "M3": 0.1},
            {"M3": 0.95, "P1": 0.2},
        ]
        self.assertTrue(
            _unordered_top1_exact(
                scores,
                ["M1", "M2", "M3"],
            )
        )

    def test_unordered_top3_coverage_fails_when_expected_tile_missing(self):
        from workspace.vision.opponent_public_meld_mobilenet import (
            _unordered_topk_covers_expected,
        )

        scores = [
            {"M1": 0.9, "P1": 0.8, "P2": 0.7},
            {"M2": 0.9, "P3": 0.8, "P4": 0.7},
            {"P5": 0.9, "P6": 0.8, "P7": 0.7},
        ]
        self.assertFalse(
            _unordered_topk_covers_expected(
                scores,
                ["M1", "M2", "M3"],
                count=3,
            )
        )

    def test_multi_frame_mean_preserves_three_face_slots(self):
        from workspace.vision.opponent_public_meld_mobilenet import (
            _mean_score_rows,
        )

        frames = [
            [
                {"M1": 0.4, "M2": 0.2},
                {"M1": 0.1, "M2": 0.7},
                {"M3": 0.8, "P1": 0.1},
            ],
            [
                {"M1": 0.6, "M2": 0.1},
                {"M1": 0.3, "M2": 0.5},
                {"M3": 0.6, "P1": 0.3},
            ],
        ]
        mean = _mean_score_rows(frames)
        self.assertEqual(len(mean), 3)
        self.assertAlmostEqual(mean[0]["M1"], 0.5)
        self.assertAlmostEqual(mean[1]["M2"], 0.6)
        self.assertAlmostEqual(mean[2]["M3"], 0.7)

    def test_runtime_acceptance_is_not_calibrated_by_this_evaluator(self):
        from workspace.vision.opponent_public_meld_mobilenet import (
            RUNTIME_IDENTITY_THRESHOLD,
        )

        self.assertEqual(
            RUNTIME_IDENTITY_THRESHOLD,
            0.82,
        )


if __name__ == "__main__":
    unittest.main()
