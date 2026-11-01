from __future__ import annotations

import importlib.util
import unittest

VISION = all(importlib.util.find_spec(name) is not None for name in ("PIL", "cv2", "numpy"))


@unittest.skipUnless(VISION, "Pillow/OpenCV/numpy are optional in core-only installs")
class PublicMeldStructureFrameBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PIL import Image, ImageDraw
        from workspace.vision.public_meld_structure_frame_bridge import (
            review_public_meld_structure_frame,
        )
        from workspace.vision.public_observers import MeldSnapshotObserver
        from workspace.vision.public_tile_detector import PublicGeometryCandidate

        cls.Image = Image
        cls.ImageDraw = ImageDraw
        cls.review_frame = staticmethod(review_public_meld_structure_frame)
        cls.Observer = MeldSnapshotObserver
        cls.Candidate = PublicGeometryCandidate

    def _image(self):
        image = self.Image.new("RGB", (1108, 512), (0, 75, 78))
        draw = self.ImageDraw.Draw(image)
        for left in (585, 610, 635, 661, 686, 711):
            draw.rectangle((left, 15, left + 20, 43), fill=(235, 235, 225))
        return image

    def _group(self, bbox, frame):
        x, y, width, height = bbox
        return self.Candidate(
            pixel_bbox=bbox,
            normalized_bbox=(x / 1108, y / 512, width / 1108, height / 512),
            geometry_kind="top_group",
            confidence=.84,
            fill_ratio=.75,
            frame=frame,
            session="round8",
        )

    def _review(self, groups, frame, *, empty_verified=False):
        return self.review_frame(
            self._image(), groups,
            timestamp_seconds=frame / 30,
            actor="opponent", source_session="round8", stream_epoch=0,
            frame_index=frame, source_frame_verified=True,
            public_meld_region_verified=True,
            empty_meld_set_verified=empty_verified,
            evidence_refs=(f"private:frame:{frame}",),
        )

    def test_empty_snapshot_requires_independent_verification(self):
        unverified = self._review((), 100)
        verified = self._review((), 101, empty_verified=True)
        self.assertFalse(unverified.snapshot.trusted)
        self.assertTrue(verified.snapshot.trusted)
        self.assertEqual(verified.snapshot.groups, ())

    def test_two_flat_groups_become_complete_two_group_snapshot(self):
        groups = (
            self._group((583, 13, 75, 33), 200),
            self._group((659, 13, 76, 33), 200),
        )
        review = self._review(groups, 200)
        self.assertTrue(review.snapshot.trusted)
        self.assertEqual(len(review.snapshot.groups), 2)
        self.assertEqual([len(group.tiles) for group in review.snapshot.groups], [3, 3])
        self.assertEqual(review.to_dict()["action_kind"], "UNKNOWN")
        self.assertFalse(review.to_dict()["safe_for_runtime"])

    def test_existing_group_plus_new_group_emits_one_three_face_meld_delta(self):
        observer = self.Observer(settle_frames=2)
        old = (self._group((659, 13, 76, 33), 300),)
        for frame in (300, 301):
            old_frame = (self._group((659, 13, 76, 33), frame),)
            out = observer.observe(self._review(old_frame, frame).snapshot)
        self.assertTrue(out.stable)
        self.assertIsNone(out.observation)
        self.assertIn("meld_baseline_established", out.issues)

        for frame in (320, 321):
            current = (
                self._group((583, 13, 75, 33), frame),
                self._group((659, 13, 76, 33), frame),
            )
            out = observer.observe(self._review(current, frame).snapshot)
        self.assertTrue(out.stable)
        self.assertIsNotNone(out.observation)
        self.assertEqual(out.observation.details["group_size"], 3)
        self.assertNotIn("previous_group_size", out.observation.details)
        self.assertFalse(out.observation.details["tile_identity_complete"])


if __name__ == "__main__":
    unittest.main()
