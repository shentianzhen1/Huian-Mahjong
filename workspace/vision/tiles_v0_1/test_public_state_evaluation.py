from types import SimpleNamespace
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from .evaluate_public_state import (
    evaluate_public_state_manifest,
    load_public_state_manifest,
)
from .public_state import PublicStateObservation


def fake_frame(score, hand, remaining, *, mode="direct", issues=()):
    return SimpleNamespace(
        score=SimpleNamespace(score_pair=score, mode=mode),
        status=SimpleNamespace(
            hand_number=hand,
            remaining_tiles=remaining,
        ),
        issues=tuple(issues),
    )


def observation(score, hand, remaining, *, issues=(), votes=2):
    return PublicStateObservation(
        top_right_score=score[0] if score is not None else None,
        bottom_left_score=score[1] if score is not None else None,
        hand_number=hand,
        remaining_tiles=remaining,
        score_votes=votes if score is not None else 0,
        hand_votes=votes if hand is not None else 0,
        remaining_votes=votes if remaining is not None else 0,
        issues=tuple(issues),
        safe_for_executor=False,
    )


class FakeReader:
    def __init__(self, windows):
        self.windows = iter(windows)
        self.previous_seen = []

    def read_window(
            self, images, *, previous=None, expected_scores=None,
            minimum_votes=2):
        self.previous_seen.append(previous)
        frames, fused = next(self.windows)
        if len(images) != len(frames):
            raise AssertionError("fake window/image count mismatch")
        return SimpleNamespace(frames=tuple(frames), observation=fused)


class PublicStateBatchEvaluationTests(unittest.TestCase):
    def _write_image(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (32, 16), "black").save(path)

    def test_batch_reports_raw_and_fused_metrics_separately(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("a1.png", "a2.png", "b1.png"):
                self._write_image(root / name)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "samples": [
                    {
                        "id": "hand1_t10",
                        "frames": ["a1.png", "a2.png"],
                        "truth": {
                            "hand_number": 1,
                            "top_right_score": 1000,
                            "bottom_left_score": 1000,
                            "remaining_tiles": 107,
                        },
                    },
                    {
                        "id": "hand2_t10",
                        "frame": "b1.png",
                        "truth": {
                            "hand_number": 2,
                            "top_right_score": 1026,
                            "bottom_left_score": 974,
                            "remaining_tiles": 108,
                        },
                    },
                ]
            }), encoding="utf-8")

            first = observation((1000, 1000), 1, 107)
            second = observation((1026, 974), 2, 108)
            reader = FakeReader([
                (
                    [
                        fake_frame((1000, 1000), 1, 107),
                        fake_frame(
                            (1000, 1000), None, 107,
                            issues=("hand_unreadable",),
                        ),
                    ],
                    first,
                ),
                (
                    [
                        fake_frame((1026, 974), 2, 107),
                    ],
                    second,
                ),
            ])

            report = evaluate_public_state_manifest(
                manifest, reader=reader, minimum_votes=1)

            self.assertEqual(report["timepoints"], 2)
            self.assertEqual(report["frames"], 3)
            self.assertEqual(
                report["raw_frame"]["score_pair"]["correct"], 3)
            self.assertEqual(
                report["raw_frame"]["hand_number"]["readable"], 2)
            self.assertEqual(
                report["raw_frame"]["remaining_tiles"]["correct"], 2)
            self.assertEqual(
                report["raw_frame"]["complete_exact"]["correct"], 1)
            self.assertEqual(
                report["raw_frame"]["issue_counts"],
                {"hand_unreadable": 1},
            )

            fused = report["fused_window"]
            self.assertEqual(fused["complete_state"]["readable"], 2)
            self.assertEqual(fused["complete_state"]["correct"], 2)
            self.assertEqual(fused["complete_state"]["exact_rate"], 1.0)
            self.assertFalse(report["safe_for_executor"])

            self.assertIsNone(reader.previous_seen[0])
            self.assertIs(reader.previous_seen[1], first)

    def test_untrusted_fused_state_is_not_carried_forward(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("a.png", "b.png"):
                self._write_image(root / name)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "samples": [
                    {
                        "frame": "a.png",
                        "hand": 1,
                        "top_right_score": 1000,
                        "bottom_left_score": 1000,
                        "remaining_tiles": 107,
                    },
                    {
                        "frame": "b.png",
                        "hand": 2,
                        "top_right_score": 1026,
                        "bottom_left_score": 974,
                        "remaining_tiles": 108,
                    },
                ]
            }), encoding="utf-8")

            untrusted = observation(
                (1000, 1000), 1, 107, issues=("score_consensus",), votes=1)
            trusted = observation((1026, 974), 2, 108, votes=1)
            reader = FakeReader([
                ([fake_frame((1000, 1000), 1, 107)], untrusted),
                ([fake_frame((1026, 974), 2, 108)], trusted),
            ])
            evaluate_public_state_manifest(
                manifest, reader=reader, minimum_votes=1)
            self.assertIsNone(reader.previous_seen[0])
            self.assertIsNone(reader.previous_seen[1])

    def test_fusion_marks_fully_unreadable_window_invalid(self):
        from .public_state import PublicStateCandidate, fuse_public_state

        result = fuse_public_state(
            [PublicStateCandidate(), PublicStateCandidate()],
            minimum_votes=2,
        )
        self.assertIsNone(result.score_pair)
        self.assertIsNone(result.hand_number)
        self.assertIsNone(result.remaining_tiles)
        self.assertEqual(
            result.issues,
            ("score_unreadable", "hand_unreadable", "remaining_unreadable"),
        )
        self.assertFalse(result.valid)
        self.assertFalse(result.safe_for_executor)

    def test_fusion_distinguishes_unreadable_from_disagreement(self):
        from .public_state import PublicStateCandidate, fuse_public_state

        result = fuse_public_state(
            [
                PublicStateCandidate(1000, 1000, 1, 107),
                PublicStateCandidate(1026, 974, 2, 106),
            ],
            minimum_votes=2,
        )
        self.assertIn("score_consensus", result.issues)
        self.assertIn("hand_consensus", result.issues)
        self.assertIn("remaining_consensus", result.issues)
        self.assertNotIn("score_unreadable", result.issues)
        self.assertNotIn("hand_unreadable", result.issues)
        self.assertNotIn("remaining_unreadable", result.issues)

    def test_manifest_rejects_invalid_truth_and_empty_frames(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            invalid_score = root / "bad_score.json"
            invalid_score.write_text(json.dumps({
                "samples": [{
                    "frame": "x.png",
                    "hand": 1,
                    "top_right_score": 1000,
                    "bottom_left_score": 999,
                    "remaining_tiles": 100,
                }]
            }), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_public_state_manifest(invalid_score)

            invalid_frames = root / "bad_frames.json"
            invalid_frames.write_text(json.dumps({
                "samples": [{
                    "frames": [],
                    "hand": 1,
                    "top_right_score": 1000,
                    "bottom_left_score": 1000,
                    "remaining_tiles": 100,
                }]
            }), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_public_state_manifest(invalid_frames)


if __name__ == "__main__":
    unittest.main()
