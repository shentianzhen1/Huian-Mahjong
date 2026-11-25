from __future__ import annotations

import importlib.util
import unittest

VISION = all(importlib.util.find_spec(name) is not None for name in ("PIL", "cv2", "numpy"))


@unittest.skipUnless(VISION, "Pillow/OpenCV/numpy are optional in core-only installs")
class PublicMeldStructureSnapshotBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PIL import Image, ImageDraw
        from workspace.vision.issue69_public_replay_adapters import meld_observation_candidate
        from workspace.vision.issue69_temporal_reconstruction import reconstruct_public_candidates
        from workspace.vision.public_meld_structure_snapshot_bridge import review_public_meld_structure_snapshot
        from workspace.vision.public_observers import MeldSnapshotObserver
        from workspace.vision.public_tile_detector import PublicGeometryCandidate

        cls.Image = Image
        cls.ImageDraw = ImageDraw
        cls.bridge = staticmethod(review_public_meld_structure_snapshot)
        cls.Observer = MeldSnapshotObserver
        cls.Candidate = PublicGeometryCandidate
        cls.adapt = staticmethod(meld_observation_candidate)
        cls.reconstruct = staticmethod(reconstruct_public_candidates)

    def _candidate(self, bbox, frame):
        width, height = 1108, 512
        x, y, w, h = bbox
        return self.Candidate(
            pixel_bbox=bbox,
            normalized_bbox=(x / width, y / height, w / width, h / height),
            geometry_kind="bottom_group",
            confidence=.84,
            fill_ratio=.75,
            frame=frame,
            session="round6",
        )

    def _flat(self):
        image = self.Image.new("RGB", (1108, 512), (0, 75, 78))
        draw = self.ImageDraw.Draw(image)
        for x in (101, 146, 191):
            draw.rectangle((x, 431, x + 40, 503), fill=(235, 235, 225))
        return image

    def _stacked(self):
        image = self.Image.new("RGB", (1108, 512), (0, 75, 78))
        draw = self.ImageDraw.Draw(image)
        for x in (101, 146, 191):
            draw.rectangle((x, 431, x + 40, 503), fill=(235, 235, 225))
        draw.rectangle((146, 418, 186, 473), fill=(235, 235, 225))
        return image

    def _review(self, image, bbox, frame, verified=True):
        return self.bridge(
            image, self._candidate(bbox, frame),
            timestamp_seconds=frame / 30,
            actor="player", source_session="round6", stream_epoch=0,
            frame_index=frame, source_frame_verified=verified,
            public_meld_region_verified=verified,
            evidence_refs=(f"private:frame:{frame}",),
        )

    def test_flat_and_stacked_map_to_unknown_identity_three_and_four_faces(self):
        flat = self._review(self._flat(), (99, 429, 140, 78), 3321)
        stacked = self._review(self._stacked(), (99, 416, 140, 91), 3363)
        self.assertTrue(flat.snapshot.trusted)
        self.assertTrue(stacked.snapshot.trusted)
        self.assertEqual(flat.structural_face_count, 3)
        self.assertEqual(stacked.structural_face_count, 4)
        self.assertEqual(flat.snapshot.groups[0].tiles, (None,) * 3)
        self.assertEqual(stacked.snapshot.groups[0].tiles, (None,) * 4)
        self.assertEqual(flat.to_dict()["action_kind"], "UNKNOWN")
        self.assertFalse(stacked.to_dict()["safe_for_runtime"])

    def test_unverified_source_fails_closed(self):
        review = self._review(self._flat(), (99, 429, 140, 78), 3321, verified=False)
        self.assertFalse(review.snapshot.trusted)
        self.assertEqual(review.snapshot.groups, ())
        self.assertIsNone(review.structural_face_count)

    def test_flat_to_stacked_flows_to_replay_upgrade_candidate_without_add_kong(self):
        observer = self.Observer(settle_frames=2)
        for frame in (3320, 3321):
            out = observer.observe(self._review(
                self._flat(), (99, 429, 140, 78), frame,
            ).snapshot)
        self.assertTrue(out.stable)
        self.assertIsNone(out.observation)
        self.assertIn("meld_baseline_established", out.issues)

        for frame in (3362, 3363):
            out = observer.observe(self._review(
                self._stacked(), (99, 416, 140, 91), frame,
            ).snapshot)
        self.assertTrue(out.stable)
        self.assertIsNotNone(out.observation)
        obs = out.observation
        self.assertEqual(obs.details["previous_group_size"], 3)
        self.assertEqual(obs.details["group_size"], 4)
        self.assertFalse(obs.details["tile_identity_complete"])

        candidate = self.adapt(obs, source_sha256="a" * 64)
        report = self.reconstruct(
            [candidate], claim_window_seconds=1.0, assembly_delay_seconds=0.0,
        )
        self.assertEqual(len(report["meld_upgrade_candidates"]), 1)
        upgrade = report["meld_upgrade_candidates"][0]
        self.assertEqual(upgrade["previous_group_size"], 3)
        self.assertEqual(upgrade["current_group_size"], 4)
        self.assertEqual(upgrade["action_kind"], "UNKNOWN")
        self.assertFalse(any(row["kind"] == "ADD_KONG" for row in report["actions"]))


if __name__ == "__main__":
    unittest.main()
