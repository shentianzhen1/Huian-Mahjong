"""Contract-only load checks for a frozen real-video *development* annotation.

These tests prove only schema/provenance integrity of manually frozen truth.
They are NOT real model accuracy tests; no machine predictions are evaluated.
"""
from __future__ import annotations

from pathlib import Path
import unittest

from workspace.vision.action_attribution_eval import load_truth


ROOT = Path(__file__).resolve().parents[1]
TRUTH_FILE = (
    ROOT / "references" / "vision" / "2026-09-23"
    / "hand01_12_25_action_truth.development.frozen.json"
)
SOURCE_SHA256 = (
    "1560c1e04a632f07dc5f53947ba3080ed93ff927a7bd028a457f3415b0bc69a3"
)


class Hand01FrozenDevelopmentTruthTests(unittest.TestCase):
    def test_loads_frozen_development_annotation_without_predictions(self):
        review = load_truth(TRUTH_FILE)
        self.assertTrue(review.truth_frozen)
        self.assertEqual(review.review_kind, "development_continuous_video")
        self.assertEqual(review.source_session, "match_evidence_001_hand_01")
        self.assertEqual(review.source_sha256, SOURCE_SHA256)
        self.assertEqual(len(review.spans), 1)
        self.assertEqual(len(review.events), 4)
        scope = review.spans[0]
        self.assertEqual(
            (scope.stream_epoch, scope.start_seconds, scope.end_seconds),
            (0, 12, 25),
        )
        self.assertEqual((scope.first_frame, scope.last_frame), (348, 725))
        self.assertEqual(
            [(e.frame, e.kind, e.actor) for e in review.events],
            [
                (404, "DISCARD", "opponent"),
                (490, "DISCARD", "player"),
                (587, "DISCARD", "opponent"),
                (685, "DISCARD", "player"),
            ],
        )
        # User only confirmed source-specific screen-side mapping, not
        # independent turn state or normalized public-region tile identity.
        self.assertTrue(all(e.turn_actor is None for e in review.events))
        self.assertTrue(all(e.tile is None for e in review.events))
        self.assertTrue(all(e.evidence_refs for e in review.events))


if __name__ == "__main__":
    unittest.main()
