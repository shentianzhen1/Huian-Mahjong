import unittest

from workspace.vision.tiles_runtime_v0_2.whole_hand_error_analysis import (
    analyze_raw_confusions,
)


class WholeHandRawConfusionTests(unittest.TestCase):
    def test_reports_wrong_top1_even_when_below_accept_threshold(self):
        manifest = {
            "schema_version": "vision_runtime_v0_2_whole_hand_eval_manifest_v0_1",
            "confidence_threshold": 0.82,
            "hands": [
                {
                    "sample_id": "dev-hand",
                    "split": "development",
                    "original_match_group": "match-a",
                    "source_session": "session-a",
                    "game_id": "round-1",
                    "truth_status": "reviewed_complete",
                    "slots": [
                        {
                            "slot": 0,
                            "truth_tile": "M1",
                            "detection_status": "matched",
                            "crop_status": "ok",
                            "crop_ref": "private://m1",
                            "predictions": {
                                "template": {"tile_id": "M3", "confidence": 0.90}
                            },
                        },
                        {
                            "slot": 1,
                            "truth_tile": "P2",
                            "detection_status": "matched",
                            "crop_status": "shadowed",
                            "crop_ref": "private://p2",
                            "predictions": {
                                "template": {"tile_id": "P3", "confidence": 0.50}
                            },
                        },
                        {
                            "slot": 2,
                            "truth_tile": "S4",
                            "detection_status": "matched",
                            "crop_status": "ok",
                            "crop_ref": "private://s4",
                            "predictions": {
                                "template": {"tile_id": "S4", "confidence": 0.91}
                            },
                        },
                    ],
                    "extra_detections": [],
                    "capture_to_advice_ms": {},
                }
            ],
        }

        report = analyze_raw_confusions(manifest, "template")

        self.assertEqual(report["raw_predicted_tiles"], 3)
        self.assertEqual(report["raw_correct_tiles"], 1)
        self.assertAlmostEqual(report["raw_tile_accuracy"], 1 / 3)
        self.assertEqual(
            report["raw_class_confusions"],
            {"M1->M3": 1, "P2->P3": 1},
        )
        self.assertEqual(
            report["raw_confusions_by_crop_status"],
            {"ok": {"M1->M3": 1}, "shadowed": {"P2->P3": 1}},
        )


if __name__ == "__main__":
    unittest.main()
