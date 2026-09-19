import unittest

from huian._legacy import env
from workspace.ai import PlayerObservation
from workspace.simulator import (DealInCalibrationRecorder,
                                 DealInCalibrationSample,
                                 summarize_deal_in_calibration)


def observation(seat=0, phase="AFTER_DRAW"):
    hand = (
        "M1","M2","M3","M4","M5","M6",
        "P1","P2","P3","P4","P5",
        "S1","S2","S3","E","E","R",
    ) if seat == 0 else ("M7",) * 16
    return PlayerObservation(
        seat=seat, hand=hand, gold_tile="P9", phase=phase,
        dealer=0, wall_remaining=60,
        discards=((), ()), flowers=((), ()), melds=((), ()),
    )


class DealInCalibrationTests(unittest.TestCase):
    def test_recorder_labels_only_after_discard_hu_response(self):
        recorder = DealInCalibrationRecorder(hand_seed=7, mc_samples=4)
        recorder.record_discard(observation(0), "M1")
        self.assertIsNotNone(recorder.pending)

        hu = env.Action(1, env.ActionType.HU, tile="M1")
        recorder.observe_turn(observation(1, "AFTER_DISCARD"), [hu])
        self.assertIsNone(recorder.pending)
        self.assertEqual(len(recorder.samples), 1)
        self.assertTrue(recorder.samples[0].actual_deal_in)
        self.assertEqual(recorder.samples[0].tile, "M1")
        self.assertEqual(recorder.samples[0].mc_samples, 4)

    def test_non_discard_turn_clears_pending_as_negative(self):
        recorder = DealInCalibrationRecorder(hand_seed=8, mc_samples=4)
        recorder.record_discard(observation(0), "M1")
        # A self-draw HU on a later phase must not be mistaken for Ron.
        hu = env.Action(1, env.ActionType.HU, tile="M7")
        recorder.observe_turn(observation(1, "AFTER_DRAW"), [hu])
        self.assertEqual(len(recorder.samples), 1)
        self.assertFalse(recorder.samples[0].actual_deal_in)

    def test_finish_hand_censors_unlabelled_last_discard(self):
        recorder = DealInCalibrationRecorder(hand_seed=9, mc_samples=2)
        recorder.record_discard(observation(0), "M1")
        recorder.finish_hand()
        self.assertIsNone(recorder.pending)
        self.assertEqual(recorder.censored_discards, 1)
        self.assertEqual(recorder.samples, [])

    def test_summary_reports_brier_auc_and_bins(self):
        rows = (
            DealInCalibrationSample(1, 0, 0, "M1", 0.9, True, 10, 9, 0, 16, 50),
            DealInCalibrationSample(1, 1, 1, "M2", 0.8, True, 10, 8, 0, 16, 49),
            DealInCalibrationSample(1, 2, 0, "M3", 0.2, False, 10, 2, 0, 16, 48),
            DealInCalibrationSample(1, 3, 1, "M4", 0.1, False, 10, 1, 0, 16, 47),
        )
        report = summarize_deal_in_calibration(
            rows, hands_attempted=2,
            hand_status_counts={"COMPLETED": 2}, censored_discards=1)
        self.assertEqual(report.labelled_discards, 4)
        self.assertEqual(report.positive_deal_ins, 2)
        self.assertEqual(report.prevalence, 0.5)
        self.assertAlmostEqual(report.mean_prediction, 0.5)
        self.assertAlmostEqual(report.mean_prediction_positive, 0.85)
        self.assertAlmostEqual(report.mean_prediction_negative, 0.15)
        self.assertAlmostEqual(report.brier_score, 0.025)
        self.assertAlmostEqual(report.constant_base_rate_brier, 0.25)
        self.assertEqual(report.auc, 1.0)
        self.assertEqual(report.censored_discards, 1)
        self.assertEqual(report.hand_status_counts, {"COMPLETED": 2})

    def test_summary_handles_no_labels(self):
        report = summarize_deal_in_calibration(())
        self.assertEqual(report.labelled_discards, 0)
        self.assertIsNone(report.prevalence)
        self.assertIsNone(report.brier_score)
        self.assertIsNone(report.auc)
        self.assertTrue(all(item.count == 0 for item in report.bins))

    def test_invalid_recorder_inputs_are_rejected(self):
        for value in (0, -1, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                DealInCalibrationRecorder(hand_seed=1, mc_samples=value)
        with self.assertRaises(ValueError):
            DealInCalibrationRecorder(hand_seed=True, mc_samples=4)


if __name__ == "__main__":
    unittest.main()
