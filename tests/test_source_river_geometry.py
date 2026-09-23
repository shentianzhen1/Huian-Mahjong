"""No-private-video CI regression for source-scoped river pixels."""
from dataclasses import replace
import importlib.util
import unittest


VISION_AVAILABLE = all(importlib.util.find_spec(name) is not None
                       for name in ("cv2", "numpy", "PIL"))
SHA = "a" * 64
SESSION = "synthetic_reviewed_hand01"
SIZE = (1046, 480)


@unittest.skipUnless(VISION_AVAILABLE, "Vision dependencies are optional in core CI")
class SourceRiverGeometryTests(unittest.TestCase):
    def setUp(self):
        import numpy as np
        from PIL import Image
        from workspace.vision.public_tile_detector import (
            PublicGeometryCandidate, PublicGeometryFrame,
        )
        from workspace.vision.source_river_geometry import (
            RiverManifest, RiverZone, qualify_river_frame,
        )
        self.np = np
        self.Image = Image
        self.Candidate = PublicGeometryCandidate
        self.Frame = PublicGeometryFrame
        self.RiverZone = RiverZone
        self.qualify = qualify_river_frame
        self.manifest = RiverManifest(
            SESSION, SHA, SIZE,
            (RiverZone("opponent", (.56, .218, .11, .087), (.024, .030), (.058, .070)),
             RiverZone("player", (.297, .519, .125, .083), (.029, .037), (.050, .066))),
            True, True,
        )

    def candidate(self, box, kind="single_face"):
        return self.Candidate(
            pixel_bbox=box,
            normalized_bbox=tuple(round(value / limit, 6) for value, limit in zip(
                box, (SIZE[0], SIZE[1], SIZE[0], SIZE[1])
            )),
            geometry_kind=kind, confidence=.82, fill_ratio=.9,
            frame=7, session=SESSION,
        )

    def test_exact_source_scope_and_no_promotion(self):
        frame = self.Frame((), (), frame=7, session=SESSION)
        image = self.Image.new("RGB", SIZE)
        result = self.qualify(image, frame, manifest=self.manifest, actual_sha256=SHA)
        self.assertEqual(result.actor_trust, {"player": True, "opponent": True})
        with self.assertRaisesRegex(ValueError, "session/hash"):
            self.qualify(image, frame, manifest=self.manifest, actual_sha256="b" * 64)
        with self.assertRaisesRegex(ValueError, "session/hash"):
            self.qualify(image, replace(frame, session="wrong"),
                         manifest=self.manifest, actual_sha256=SHA)
        with self.assertRaisesRegex(ValueError, "resolution"):
            self.qualify(self.Image.new("RGB", (1045, 480)), frame,
                         manifest=self.manifest, actual_sha256=SHA)
        with self.assertRaisesRegex(ValueError, "holdout"):
            replace(self.manifest, development_only=False)
        with self.assertRaisesRegex(ValueError, "overlap"):
            replace(self.manifest, zones=(
                self.manifest.zone("opponent"),
                self.RiverZone("player", (.60, .24, .08, .08), (.029, .037), (.05, .066)),
            ))
        with self.assertRaisesRegex(ValueError, "normalized"):
            self.RiverZone("opponent", (float("nan"), .2, .1, .1),
                           (.024, .03), (.058, .07))

    def test_reviewed_interval_fails_closed(self):
        scoped = replace(self.manifest, reviewed_frame_span=(5, 8))
        frame = self.Frame((), (), frame=9, session=SESSION)
        with self.assertRaisesRegex(ValueError, "outside source-reviewed"):
            self.qualify(self.Image.new("RGB", SIZE), frame,
                         manifest=scoped, actual_sha256=SHA)
        with self.assertRaisesRegex(ValueError, "reviewed_frame_span"):
            replace(self.manifest, reviewed_frame_span=(9, 5))

    def test_negative_hand_animation_and_decorative_candidates(self):
        boxes = (
            (646, 110, 27, 30), (325, 257, 35, 27),  # public rivers
            (646, 40, 28, 30),  # opponent's hand
            (480, 170, 28, 30),  # central animation
            (325, 394, 35, 27),  # detailed own hand
            (900, 110, 28, 30),  # unrelated decoration
        )
        frame = self.Frame(tuple(self.candidate(box) for box in boxes),
                           (), frame=7, session=SESSION)
        result = self.qualify(self.Image.new("RGB", SIZE), frame,
                              manifest=self.manifest, actual_sha256=SHA)
        self.assertEqual({candidate.pixel_bbox
                          for candidate in result.filtered_frame.candidates},
                         {boxes[0], boxes[1]})
        self.assertTrue(all(result.actor_trust.values()))

    def test_visible_two_face_seam_is_required_for_split(self):
        pixels = self.np.zeros((480, 1046, 3), dtype=self.np.uint8)
        pixels[110:140, 618:674] = 238
        pixels[110:124, 646:647] = 45  # one visible dark join
        image = self.Image.fromarray(pixels)
        frame = self.Frame((self.candidate((618, 110, 56, 30)),), (), 7, SESSION)
        result = self.qualify(image, frame, manifest=self.manifest, actual_sha256=SHA)
        self.assertTrue(result.actor_trust["opponent"])
        left, right = sorted(result.filtered_frame.candidates,
                             key=lambda candidate: candidate.pixel_bbox[0])
        self.assertEqual(left.geometry_kind, "river_split_face")
        self.assertEqual(right.geometry_kind, "river_split_face")
        self.assertEqual(left.pixel_bbox[0], 618)
        self.assertEqual(right.pixel_bbox[0], left.pixel_bbox[0] + left.pixel_bbox[2])
        self.assertEqual(left.pixel_bbox[2] + right.pixel_bbox[2], 56)
        self.assertTrue(all(candidate.to_dict()["tile_id"] == "UNKNOWN"
                            for candidate in result.filtered_frame.candidates))

    def test_wide_box_without_visible_seam_abstains(self):
        image = self.Image.new("RGB", SIZE, (238, 238, 238))
        frame = self.Frame((self.candidate((618, 110, 56, 30)),
                            self.candidate((325, 257, 35, 27))), (), 7, SESSION)
        result = self.qualify(image, frame, manifest=self.manifest,
                              actual_sha256=SHA)
        self.assertEqual(result.actor_trust, {"opponent": False, "player": True})
        self.assertIn("opponent:unsplit_wide_river_component", result.issues)
        self.assertEqual([candidate.pixel_bbox
                          for candidate in result.filtered_frame.candidates],
                         [(325, 257, 35, 27)])


if __name__ == "__main__":
    unittest.main()
