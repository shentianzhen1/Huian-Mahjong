from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

VISION = all(
    importlib.util.find_spec(name) is not None
    for name in ("PIL", "cv2", "numpy")
)


ROOT = Path(__file__).resolve().parents[1]
CALIBRATION = ROOT / "references/vision/2026-09-22/public_detector_calibration_v0_1.json"
IDENTITY = ROOT / "references/vision/2026-09-22/public_identity_labels_v0_1.json"


def _best_bottom_group(detection, target_bbox):
    from workspace.vision.public_tile_detector import target_coverage

    candidates = [
        candidate
        for candidate in detection.candidates
        if candidate.geometry_kind == "bottom_group"
    ]
    return max(
        candidates,
        key=lambda candidate: target_coverage(candidate.normalized_bbox, target_bbox),
        default=None,
    )


@unittest.skipUnless(VISION, "Pillow/OpenCV/numpy are optional in core-only installs")
class PublicMeldFaceSegmentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PIL import Image
        from workspace.vision.public_identity_labels import load_public_identity_manifest
        from workspace.vision.public_meld_face_segmentation import (
            segment_regular_meld_faces,
        )
        from workspace.vision.public_tile_detector import (
            PublicGeometryCandidate,
            detect_public_tile_geometry,
            target_coverage,
        )

        cls.Image = Image
        cls.segment_regular_meld_faces = staticmethod(segment_regular_meld_faces)
        cls.PublicGeometryCandidate = PublicGeometryCandidate
        cls.detect_public_tile_geometry = staticmethod(detect_public_tile_geometry)
        cls.target_coverage = staticmethod(target_coverage)
        cls.calibration = json.loads(CALIBRATION.read_text(encoding="utf-8"))
        cls.labels = load_public_identity_manifest(IDENTITY)

    def test_regular_synthetic_group_splits_into_three_unknown_faces(self):
        group = self.PublicGeometryCandidate(
            pixel_bbox=(100, 400, 132, 66),
            normalized_bbox=(0.10, 0.80, 0.132, 0.132),
            geometry_kind="bottom_group",
            confidence=0.91,
            fill_ratio=0.88,
            frame=10,
            session="synthetic",
        )
        result = self.segment_regular_meld_faces(group, (1000, 500))
        self.assertEqual(len(result.faces), 3)
        self.assertEqual([face.face_index for face in result.faces], [0, 1, 2])
        self.assertEqual(sum(face.pixel_bbox[2] for face in result.faces), 132)
        report = result.to_dict()
        self.assertTrue(report["regular_three_face_row"])
        self.assertTrue(all(face["tile_id"] == "UNKNOWN" for face in report["faces"]))
        self.assertTrue(all(face["evidence_grade"] == "UNKNOWN" for face in report["faces"]))
        self.assertFalse(report["safe_for_runtime_identity"])
        self.assertFalse(report["safe_for_executor"])

    def test_stacked_kong_like_geometry_abstains(self):
        group = self.PublicGeometryCandidate(
            pixel_bbox=(96, 376, 136, 101),
            normalized_bbox=(0.092, 0.783, 0.130, 0.210),
            geometry_kind="bottom_group",
            confidence=0.84,
            fill_ratio=0.75,
            frame=20,
            session="synthetic",
        )
        result = self.segment_regular_meld_faces(group, (1046, 480))
        self.assertEqual(result.faces, ())
        self.assertIn("non_regular_three_face_geometry", result.issues)

    def test_non_meld_candidate_is_never_split(self):
        group = self.PublicGeometryCandidate(
            pixel_bbox=(400, 50, 48, 78),
            normalized_bbox=(0.4, 0.1, 0.048, 0.156),
            geometry_kind="single_face",
            confidence=0.80,
            fill_ratio=0.80,
            frame=30,
            session="synthetic",
        )
        result = self.segment_regular_meld_faces(group, (1000, 500))
        self.assertEqual(result.faces, ())
        self.assertEqual(result.issues, ("not_bottom_group",))

    def test_four_reviewed_regular_melds_cover_all_twelve_approved_faces(self):
        labels_by_sample = {}
        for label in self.labels.labels:
            if label.region == "public_meld":
                labels_by_sample.setdefault(label.source_calibration_sample_id, []).append(label)

        clean_samples = [
            row for row in self.calibration["samples"]
            if row["target"] == "meld" and len(row["expected_tiles"]) == 3
        ]
        self.assertEqual(len(clean_samples), 4)

        failures = []
        covered = 0
        for sample in clean_samples:
            image = self.Image.open(ROOT / sample["image_path"]).convert("RGB")
            detection = self.detect_public_tile_geometry(
                image,
                frame=sample["frame_index"],
                session=sample["source_session"],
            )
            group = _best_bottom_group(detection, tuple(sample["bbox"]))
            self.assertIsNotNone(group, sample["sample_id"])
            assert group is not None
            split = self.segment_regular_meld_faces(group, image.size)
            self.assertEqual(len(split.faces), 3, sample["sample_id"])

            reviewed = sorted(
                labels_by_sample[sample["sample_id"]],
                key=lambda label: label.bbox[0],
            )
            self.assertEqual(len(reviewed), 3, sample["sample_id"])
            for face, label in zip(split.faces, reviewed):
                score = self.target_coverage(face.normalized_bbox, label.bbox)
                if score < 0.80:
                    failures.append((sample["sample_id"], label.label_id, round(score, 6)))
                covered += 1

        self.assertEqual(covered, 12)
        self.assertEqual(failures, [])

    def test_reviewed_added_kong_group_abstains_instead_of_fabricating_four_faces(self):
        sample = next(
            row for row in self.calibration["samples"]
            if row["sample_id"] == "66fe_player_added_kong_p1_070s"
        )
        image = self.Image.open(ROOT / sample["image_path"]).convert("RGB")
        detection = self.detect_public_tile_geometry(
            image,
            frame=sample["frame_index"],
            session=sample["source_session"],
        )
        group = _best_bottom_group(detection, tuple(sample["bbox"]))
        self.assertIsNotNone(group)
        assert group is not None
        split = self.segment_regular_meld_faces(group, image.size)
        self.assertEqual(split.faces, ())
        self.assertIn("non_regular_three_face_geometry", split.issues)


if __name__ == "__main__":
    unittest.main()
