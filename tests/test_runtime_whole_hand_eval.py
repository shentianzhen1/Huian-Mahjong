import copy
import unittest

from workspace.vision.tiles_runtime_v0_2.whole_hand_eval import (
    FROZEN_CONFIDENCE_THRESHOLD,
    compare_models,
    evaluate_model,
    validate_manifest,
)


def _manifest():
    return {
        "schema_version": "vision_runtime_v0_2_whole_hand_eval_manifest_v0_1",
        "confidence_threshold": FROZEN_CONFIDENCE_THRESHOLD,
        "hands": [
            {
                "sample_id": "dev-hand-1",
                "split": "development",
                "original_match_group": "reviewed_match_a",
                "source_session": "session_a_frame_neighbors",
                "game_id": "round_1",
                "truth_status": "reviewed_complete",
                "slots": [
                    {
                        "slot": 0,
                        "truth_tile": "M1",
                        "detection_status": "matched",
                        "crop_status": "ok",
                        "crop_ref": "private://dev-hand-1/slot-0",
                        "predictions": {
                            "template": {"tile_id": "M1", "confidence": 0.91},
                            "candidate": {"tile_id": "M1", "confidence": 0.96},
                        },
                    },
                    {
                        "slot": 1,
                        "truth_tile": "M2",
                        "detection_status": "matched",
                        "crop_status": "ok",
                        "crop_ref": "private://dev-hand-1/slot-1",
                        "predictions": {
                            "template": {"tile_id": "M2", "confidence": 0.88},
                            "candidate": {"tile_id": "M2", "confidence": 0.94},
                        },
                    },
                ],
                "extra_detections": [],
                "capture_to_advice_ms": {"template": 100.0, "candidate": 120.0},
            },
            {
                "sample_id": "holdout-hand-1",
                "split": "holdout",
                "original_match_group": "reviewed_match_b",
                "source_session": "session_b",
                "game_id": "round_1",
                "truth_status": "reviewed_complete",
                "slots": [
                    {
                        "slot": 0,
                        "truth_tile": "M1",
                        "detection_status": "matched",
                        "crop_status": "ok",
                        "crop_ref": "private://holdout-hand-1/slot-0",
                        "predictions": {
                            "template": {"tile_id": "M3", "confidence": 0.90},
                            "candidate": {"tile_id": "M1", "confidence": 0.95},
                        },
                    },
                    {
                        "slot": 1,
                        "truth_tile": "M2",
                        "detection_status": "matched",
                        "crop_status": "shadowed",
                        "crop_ref": "private://holdout-hand-1/slot-1",
                        "predictions": {
                            "template": {"tile_id": "M2", "confidence": 0.85},
                            "candidate": {"tile_id": "M2", "confidence": 0.80},
                        },
                    },
                ],
                "extra_detections": [],
                "capture_to_advice_ms": {"template": 140.0, "candidate": 160.0},
            },
            {
                "sample_id": "holdout-hand-2",
                "split": "holdout",
                "original_match_group": "reviewed_match_b",
                "source_session": "session_b_adjacent_frame",
                "game_id": "round_2",
                "truth_status": "reviewed_complete",
                "slots": [
                    {
                        "slot": 0,
                        "truth_tile": "P1",
                        "detection_status": "missed",
                        "crop_status": "unreviewed",
                        "crop_ref": None,
                        "predictions": {},
                    },
                    {
                        "slot": 1,
                        "truth_tile": "P2",
                        "detection_status": "matched",
                        "crop_status": "bad_crop",
                        "crop_ref": "private://holdout-hand-2/slot-1",
                        "predictions": {
                            "template": {"tile_id": "P3", "confidence": 0.50},
                            "candidate": {"tile_id": "P2", "confidence": 0.90},
                        },
                    },
                ],
                "extra_detections": [
                    {"crop_ref": "private://holdout-hand-2/extra-0"}
                ],
                "capture_to_advice_ms": {},
            },
        ],
    }


class WholeHandEvalTests(unittest.TestCase):
    def test_threshold_is_frozen_at_point_82(self):
        manifest = _manifest()
        validate_manifest(manifest)

        manifest["confidence_threshold"] = 0.81
        with self.assertRaisesRegex(ValueError, "frozen at 0.82"):
            validate_manifest(manifest)

    def test_original_match_cannot_leak_across_splits(self):
        manifest = _manifest()
        leaked = copy.deepcopy(manifest["hands"][0])
        leaked["sample_id"] = "leaked-adjacent-frame"
        leaked["split"] = "holdout"
        leaked["source_session"] = "different_session_name_does_not_make_independent"
        manifest["hands"].append(leaked)

        with self.assertRaisesRegex(ValueError, "source leakage"):
            validate_manifest(manifest)

    def test_template_report_separates_pipeline_errors_and_whole_hand_failure(self):
        report = evaluate_model(_manifest(), "template")

        self.assertEqual(report["confidence_threshold"], 0.82)
        self.assertTrue(report["confidence_threshold_frozen"])
        self.assertFalse(report["source_session_is_independence_signal"])
        self.assertEqual(report["reviewed_complete_hands"], 3)
        self.assertEqual(report["truth_tiles"], 6)
        self.assertEqual(report["missed_detection_count"], 1)
        self.assertEqual(report["extra_detection_count"], 1)
        self.assertEqual(report["primary_outcomes"]["bad_crop"], 1)
        self.assertEqual(report["primary_outcomes"]["class_confusion"], 1)
        self.assertEqual(report["class_confusions"], {"M1->M3": 1})
        self.assertEqual(report["whole_hand_exact_count"], 1)
        self.assertEqual(report["advice_eligible_hand_count"], 2)
        self.assertEqual(report["wrong_accepted_hand_count"], 1)
        self.assertAlmostEqual(report["whole_hand_exact_rate"], 1 / 3)
        self.assertAlmostEqual(report["wrong_accepted_hand_rate"], 1 / 3)
        self.assertEqual(report["latency_ms"]["p50"], 120.0)
        self.assertEqual(report["latency_ms"]["p95"], 138.0)

    def test_partial_truth_is_not_used_as_accuracy_denominator(self):
        manifest = _manifest()
        manifest["hands"][0]["truth_status"] = "partial"

        report = evaluate_model(manifest, "template")

        self.assertEqual(report["reviewed_complete_hands"], 2)
        self.assertEqual(report["excluded_partial_hands"], 1)
        self.assertEqual(report["truth_tiles"], 4)

    def test_ab_requires_both_models_on_the_same_matched_crops(self):
        manifest = _manifest()
        del manifest["hands"][0]["slots"][0]["predictions"]["candidate"]

        with self.assertRaisesRegex(ValueError, "exact same matched crop"):
            compare_models(manifest, "template", "candidate")

    def test_ab_keeps_detector_input_fixed_and_reports_candidate_delta(self):
        report = compare_models(_manifest(), "template", "candidate")

        self.assertTrue(report["same_manifest"])
        self.assertTrue(report["same_matched_crop_requirement"])
        self.assertGreater(
            report["candidate_minus_baseline"]["raw_tile_accuracy"],
            0.0,
        )
        self.assertLess(
            report["candidate_minus_baseline"]["wrong_accepted_hand_rate"],
            0.0,
        )
        self.assertEqual(
            report["baseline"]["missed_detection_count"],
            report["candidate"]["missed_detection_count"],
        )
        self.assertEqual(
            report["baseline"]["extra_detection_count"],
            report["candidate"]["extra_detection_count"],
        )


if __name__ == "__main__":
    unittest.main()
