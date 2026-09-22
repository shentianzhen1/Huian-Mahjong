from __future__ import annotations

import json
from pathlib import Path
import unittest

from workspace.vision.public_identity_labels import (
    PUBLIC_REGIONS,
    PublicIdentityLabel,
    load_public_identity_manifest,
    pixel_bbox,
    readiness_report,
    validate_against_calibration_rows,
    verify_repository_files,
)


ROOT = Path(__file__).resolve().parents[1]
LABELS = (
    ROOT
    / "references"
    / "vision"
    / "2026-09-22"
    / "public_identity_labels_v0_1.json"
)
CALIBRATION = (
    ROOT
    / "references"
    / "vision"
    / "2026-09-22"
    / "public_detector_calibration_v0_1.json"
)


class PublicIdentityLabelsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load_public_identity_manifest(LABELS)
        cls.calibration = json.loads(
            CALIBRATION.read_text(encoding="utf-8")
        )

    def test_manifest_is_separate_development_only_public_domain(self):
        self.assertTrue(self.manifest.excluded_from_formal_promotion)
        self.assertEqual(len(self.manifest.labels), 17)
        self.assertEqual(
            {label.region for label in self.manifest.labels},
            PUBLIC_REGIONS,
        )
        self.assertTrue(
            all(label.status == "approved" for label in self.manifest.labels)
        )

    def test_region_counts_and_source_coverage(self):
        report = readiness_report(self.manifest)
        self.assertEqual(report["approved_labels"], 17)
        self.assertEqual(report["regions"]["public_action"]["labels"], 4)
        self.assertEqual(report["regions"]["public_action"]["source_sessions"], 2)
        self.assertEqual(report["regions"]["public_single"]["labels"], 1)
        self.assertEqual(report["regions"]["public_single"]["source_sessions"], 1)
        self.assertEqual(report["regions"]["public_meld"]["labels"], 12)
        self.assertEqual(report["regions"]["public_meld"]["source_sessions"], 2)

    def test_initial_labels_cover_only_a_small_subset_of_standard_classes(self):
        report = readiness_report(self.manifest)
        self.assertEqual(report["standard_class_coverage"]["covered"], 11)
        self.assertEqual(report["standard_class_coverage"]["total"], 34)
        self.assertEqual(report["cross_session_class_count"], 0)
        self.assertFalse(report["runtime_identity_ready"])
        self.assertFalse(report["formal_promotion_eligible"])

    def test_source_images_match_locked_hashes(self):
        self.assertEqual(
            verify_repository_files(self.manifest, ROOT),
            (),
        )

    def test_labels_match_detector_calibration_provenance(self):
        self.assertEqual(
            validate_against_calibration_rows(
                self.manifest,
                self.calibration["samples"],
            ),
            (),
        )

    def test_public_meld_faces_are_individual_not_whole_group_boxes(self):
        melds = [
            label
            for label in self.manifest.labels
            if label.region == "public_meld"
        ]
        self.assertEqual(len(melds), 12)
        self.assertTrue(all(label.bbox[2] < 0.05 for label in melds))
        self.assertTrue(all(label.bbox[3] < 0.15 for label in melds))

    def test_reviewed_stack_kong_is_not_falsely_face_approved(self):
        sample_ids = {
            label.source_calibration_sample_id
            for label in self.manifest.labels
        }
        self.assertNotIn(
            "66fe_player_added_kong_p1_070s",
            sample_ids,
        )

    def test_pixel_bbox_round_trip_on_1046x480_sources(self):
        action = next(
            label
            for label in self.manifest.labels
            if label.label_id == "public_action_p1"
        )
        self.assertEqual(
            pixel_bbox(action, (1046, 480)),
            (492, 42, 58, 78),
        )
        meld = next(
            label
            for label in self.manifest.labels
            if label.label_id == "public_meld_p1_a"
        )
        self.assertEqual(
            pixel_bbox(meld, (1046, 480)),
            (100, 414, 43, 60),
        )

    def test_public_schema_rejects_hand_region(self):
        seed = self.manifest.labels[0]
        with self.assertRaises(ValueError):
            PublicIdentityLabel(
                label_id="invalid_hand_region",
                source_calibration_sample_id=seed.source_calibration_sample_id,
                source_session=seed.source_session,
                source_sha256=seed.source_sha256,
                image_path=seed.image_path,
                image_sha256=seed.image_sha256,
                frame_index=seed.frame_index,
                time_ms=seed.time_ms,
                region="hand_region",
                tile_id=seed.tile_id,
                bbox=seed.bbox,
            )


if __name__ == "__main__":
    unittest.main()
