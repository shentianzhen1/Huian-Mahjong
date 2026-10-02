"""Synthetic replay/manifest tests; no private video or coordinates."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None

from workspace.vision.real_video_action_area_replay import (
    ActionAreaManifest, load_action_area_manifest,
    scan_decoded_action_area_frames,
)
from workspace.vision.public_action_area_onset import ActionAreaProfile

SHA = "a" * 64
SIZE = (960, 448)


def profile(actor):
    return ActionAreaProfile(
        actor, (.45, .35, .45, .45), (.25, .25, .65, .60),
        (.035, .09), (.07, .16), (.002, .012), (.9, 2.2),
        (.02, .5),
    )


def manifest():
    return ActionAreaManifest(
        "synthetic_source", SHA, SIZE, (0, 5),
        (profile("player"), profile("opponent")),
        12, True, True,
    )


def pixels(tile=None):
    image = np.empty((SIZE[1], SIZE[0], 3), dtype=np.uint8)
    image[:] = (130, 92, 18)
    if tile:
        x, y = tile
        image[y:y+58, x:x+46] = 224
    return image


@unittest.skipUnless(np is not None and cv2 is not None,
                     "OpenCV/numpy Vision extras not installed")
class RealVideoActionAreaReplayTests(unittest.TestCase):
    def test_synthetic_stream_emits_candidate_only_and_collapses_burst(self):
        frames = [
            pixels(), pixels(tile=(620, 250)), pixels(tile=(500, 220)),
            pixels(tile=(400, 210)), pixels(), pixels(),
        ]
        report = scan_decoded_action_area_frames(enumerate(frames), manifest())
        # Both synthetic profiles intentionally inspect the same region; this
        # tests source/actor separation, not real-room ROI calibration.
        self.assertEqual(report["collapsed_candidate_counts"],
                         {"player": 1, "opponent": 1})
        self.assertEqual(len(report["candidates"]), 2)
        self.assertTrue(all(row["tile"] == "UNKNOWN" for row in report["candidates"]))
        self.assertFalse(report["formal_promotion_evidence"])
        self.assertFalse(report["safe_for_runtime"])
        self.assertFalse(report["safe_for_executor"])

    def test_source_pts_is_carried_without_treating_frame_as_seconds(self):
        frames = [
            (index, image, index / 30)
            for index, image in enumerate((
                pixels(), pixels(tile=(620, 250)), pixels(tile=(500, 220)),
                pixels(tile=(400, 210)), pixels(), pixels(),
            ))
        ]
        report = scan_decoded_action_area_frames(frames, manifest())
        self.assertTrue(all(item["timestamp_seconds"] is not None
                            and item["timestamp_seconds"] < 1
                            for item in report["candidates"]))
        frames[2] = (2, frames[2][1], frames[1][2])
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            scan_decoded_action_area_frames(frames, manifest())

    def test_manifest_loader_and_development_guards(self):
        row = {
            "schema_version": "source_action_area_geometry_v0_1",
            "source_session": "synthetic_source", "source_sha256": SHA,
            "frame_size": list(SIZE), "reviewed_frame_span": [0, 5],
            "minimum_event_separation_frames": 12,
            "development_only": True, "excluded_from_formal_promotion": True,
            "profiles": [{
                "actor": actor, "onset_region": [.45, .35, .45, .45],
                "confirmation_region": [.25, .25, .65, .60],
                "width_ratio": [.035, .09], "height_ratio": [.07, .16],
                "area_ratio": [.002, .012], "aspect_ratio": [.9, 2.2],
                "centroid_motion_ratio": [.02, .5],
            } for actor in ("player", "opponent")],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(row), encoding="utf-8")
            loaded = load_action_area_manifest(path)
            self.assertEqual(loaded.source_session, "synthetic_source")
            row["development_only"] = False
            path.write_text(json.dumps(row), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "development-only"):
                load_action_area_manifest(path)

    def test_replay_rejects_gaps_resolution_and_out_of_span(self):
        with self.assertRaisesRegex(ValueError, "contiguous"):
            scan_decoded_action_area_frames(
                [(0, pixels()), (2, pixels()), (3, pixels())], manifest(),
            )
        with self.assertRaisesRegex(ValueError, "resolution"):
            scan_decoded_action_area_frames(
                [(0, np.zeros((447, 960, 3), np.uint8))], manifest(),
            )
        with self.assertRaisesRegex(ValueError, "outside reviewed span"):
            scan_decoded_action_area_frames([(6, pixels())], manifest())


if __name__ == "__main__":
    unittest.main()
