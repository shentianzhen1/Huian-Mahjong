"""Public-only regression for second-hand development evidence (#69).

Private video and crop pixels are not in CI. This does not promote Vision.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from workspace.vision.action_attribution_eval import load_truth
from workspace.vision.real_video_river_replay import replay_rivers
from workspace.vision.source_river_geometry import load_river_manifest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "references/vision/2026-09-23/hand02_early_river_geometry.development.json"
TRUTH = ROOT / "references/vision/2026-09-23/hand02_08_38_action_truth.development.frozen.json"
HAND1 = ROOT / "references/vision/2026-09-23/hand01_river_geometry.development.json"


class Hand02FixtureTests(unittest.TestCase):
    def test_source_and_actor_roi_locked_to_reviewed_interval(self):
        m = load_river_manifest(MANIFEST)
        self.assertEqual(m.source_session, "match_evidence_001_hand_02")
        self.assertEqual(m.frame_size, (960, 448))
        self.assertEqual(m.reviewed_frame_span, (250, 1100))
        self.assertEqual({z.actor for z in m.zones}, {"opponent", "player"})
        self.assertTrue(m.development_only)
        self.assertTrue(m.excluded_from_formal_promotion)
        self.assertNotEqual(m.source_sha256, load_river_manifest(HAND1).source_sha256)

    def test_frozen_human_timeline_keeps_tile_and_turn_unknown(self):
        m = load_river_manifest(MANIFEST)
        truth = load_truth(TRUTH)
        self.assertEqual(truth.source_sha256, m.source_sha256)
        self.assertEqual(truth.source_session, m.source_session)
        self.assertEqual(truth.review_kind, "development_continuous_video")
        self.assertTrue(truth.truth_frozen)
        self.assertEqual([(e.frame, e.actor, e.kind) for e in truth.events], [
            (299, "opponent", "DISCARD"), (491, "player", "DISCARD"),
            (690, "opponent", "DISCARD"), (987, "player", "DISCARD")
        ])
        self.assertTrue(all(e.tile is None and e.turn_actor is None for e in truth.events))
        self.assertEqual(
            (truth.spans[0].first_frame, truth.spans[0].last_frame),
            m.reviewed_frame_span,
        )

    def test_wrong_source_rejected_before_video_decode(self):
        with TemporaryDirectory() as temp:
            fake = Path(temp) / "not_reviewed.mp4"
            fake.write_bytes(b"not the private recording")
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                replay_rivers(fake, manifest_path=MANIFEST,
                              first_frame=250, last_frame=1100)

    def test_unreviewed_frame_span_rejected_before_video_decode(self):
        with TemporaryDirectory() as temp:
            fake = Path(temp) / "not_reviewed.mp4"
            fake.write_bytes(b"not the private recording")
            with self.assertRaisesRegex(ValueError, "source-reviewed river interval"):
                replay_rivers(fake, manifest_path=MANIFEST,
                              first_frame=249, last_frame=1100)
            with self.assertRaisesRegex(ValueError, "source-reviewed river interval"):
                replay_rivers(fake, manifest_path=MANIFEST,
                              first_frame=250, last_frame=1101)


if __name__ == "__main__":
    unittest.main()
