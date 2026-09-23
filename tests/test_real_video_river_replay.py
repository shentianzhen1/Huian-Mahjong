"""Synthetic full-pipeline regression; CI never needs the user's recording."""
import hashlib
import importlib.util
import json
import unittest
from unittest.mock import patch


VISION_AVAILABLE = all(importlib.util.find_spec(name) is not None
                       for name in ("cv2", "numpy", "PIL"))
WIDTH, HEIGHT = 1046, 480
SESSION = "synthetic_full_pipeline"


@unittest.skipUnless(VISION_AVAILABLE, "Vision dependencies are optional in core CI")
class RiverReplayTests(unittest.TestCase):
    def setUp(self):
        import cv2
        import numpy as np
        self.cv2 = cv2
        self.np = np
        from tempfile import TemporaryDirectory
        from pathlib import Path
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def manifest(self, sha):
        path = self.root / "synthetic_river.json"
        path.write_text(json.dumps({
            "schema_version": "source_river_geometry_v0_1",
            "source_session": SESSION,
            "source_sha256": sha,
            "frame_size": [WIDTH, HEIGHT],
            "development_only": True,
            "excluded_from_formal_promotion": True,
            "zones": [
                {"actor": "opponent", "bbox": [.56, .218, .11, .087],
                 "single_width": [.024, .03], "single_height": [.058, .07]},
                {"actor": "player", "bbox": [.297, .519, .125, .083],
                 "single_width": [.029, .037], "single_height": [.05, .066]},
            ],
        }), encoding="utf-8")
        return path

    def capture(self, count=51):
        cv2, np = self.cv2, self.np

        class SyntheticCapture:
            def __init__(self):
                self.next_frame = 0
                self.last_read = -1
                self.released = False

            def isOpened(self):
                return True

            def get(self, name):
                if name == cv2.CAP_PROP_FRAME_COUNT:
                    return count
                if name == cv2.CAP_PROP_FRAME_WIDTH:
                    return WIDTH
                if name == cv2.CAP_PROP_FRAME_HEIGHT:
                    return HEIGHT
                if name == cv2.CAP_PROP_POS_MSEC:
                    return (self.last_read + 1) * 1000 / 30
                raise AssertionError(name)

            def set(self, name, value):
                assert name == cv2.CAP_PROP_POS_FRAMES
                self.next_frame = int(value)
                return True

            def read(self):
                if self.next_frame >= count:
                    return False, None
                index = self.next_frame
                self.next_frame += 1
                self.last_read = index
                rgb = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
                rgb[:, :] = (23, 67, 47)
                if index >= 6:
                    if index < 26:
                        rgb[110:140, 646:674] = 237
                    else:
                        rgb[110:140, 618:674] = 237
                        rgb[110:124, 646:647] = 35
                if index >= 16:
                    if index < 36:
                        rgb[257:284, 325:360] = 237
                    else:
                        rgb[257:284, 325:395] = 237
                        rgb[257:269, 360:361] = 35
                if 7 <= index <= 12:
                    rgb[45:75, 646:674] = 237  # hand, outside actor river
                    rgb[170:240, 480:540] = 237  # enlarged animation
                return True, cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

            def release(self):
                self.released = True

        return SyntheticCapture()

    def test_detector_tracker_both_observers_assembler_and_evaluator(self):
        from workspace.vision.real_video_river_replay import replay_rivers
        from workspace.vision.action_attribution_eval import (
            ActionPrediction, PredictionBatch, ReviewedSpan, TruthBatch,
            TruthEvent, evaluate_attribution,
        )
        video = self.root / "synthetic.mp4"
        video.write_bytes(b"CI synthetic source, not the private recording")
        sha = hashlib.sha256(video.read_bytes()).hexdigest()
        cap = self.capture()
        with patch.object(self.cv2, "VideoCapture", return_value=cap):
            result = replay_rivers(video, manifest_path=self.manifest(sha),
                                   first_frame=0, last_frame=50)
        self.assertTrue(cap.released)
        self.assertEqual(result["frames_decoded"], 51)
        self.assertEqual(result["stream_epochs"], [0])
        self.assertFalse(result["safe_for_executor"])
        self.assertFalse(result["source_disjoint_holdout"])
        self.assertIsNone(result["development_evaluation"])
        predictions = result["machine_predictions"]["actions"]
        self.assertEqual([(p["actor"], p["kind"]) for p in predictions], [
            ("opponent", "DISCARD"), ("player", "DISCARD"),
            ("opponent", "DISCARD"), ("player", "DISCARD"),
        ])
        self.assertTrue(all(p["tile"] is None and p["turn_actor"] is None
                            and p["evidence_grade"] == "UNKNOWN"
                            for p in predictions))
        self.assertEqual(result["counts"]["opponent_river_growth_observations"], 2)
        self.assertEqual(result["counts"]["player_river_growth_observations"], 2)

        # The *synthetic* truth tests an abstention contract; no real truth
        # is ever imported into the machine stage.
        truth = TruthBatch(
            source_session=SESSION, source_sha256=sha,
            review_kind="synthetic_contract", truth_frozen=True,
            spans=(ReviewedSpan(0, 0, 3, 0, 90, ("synthetic:span",)),),
            events=tuple(TruthEvent(
                timestamp_seconds=p["timestamp_seconds"], stream_epoch=0,
                frame=i + 5, kind="DISCARD", actor=p["actor"],
                evidence_refs=(f"synthetic:truth:{i}",),
            ) for i, p in enumerate(predictions)),
        )
        typed = tuple(ActionPrediction(
            timestamp_seconds=p["timestamp_seconds"], source_session=p["source_session"],
            stream_epoch=p["stream_epoch"], kind=p["kind"], actor=p["actor"],
            evidence_grade=p["evidence_grade"], evidence_refs=tuple(p["evidence_refs"]),
            confidence=p["confidence"], tile=p["tile"], turn_actor=p["turn_actor"],
        ) for p in predictions)
        metrics = evaluate_attribution(truth, PredictionBatch(sha, typed))
        self.assertEqual(metrics["abstentions"], 4)
        self.assertEqual(metrics["false_negatives"], 4)
        self.assertEqual(metrics["true_positives"], 0)
        self.assertIsNone(metrics["actor_accuracy_on_aligned"])

    def test_wrong_video_sha_aborts_before_opening_capture(self):
        from workspace.vision.real_video_river_replay import replay_rivers
        video = self.root / "wrong.mp4"
        video.write_bytes(b"changed video bytes")
        with patch.object(self.cv2, "VideoCapture",
                          side_effect=AssertionError("should not decode")):
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                replay_rivers(video, manifest_path=self.manifest("a" * 64),
                              first_frame=0, last_frame=10)


if __name__ == "__main__":
    unittest.main()
