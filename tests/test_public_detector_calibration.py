from __future__ import annotations

from pathlib import Path
import unittest

from workspace.vision.public_detector_calibration import (
    CalibrationSample,
    bbox_review_template,
    load_manifest,
    pending_bbox_samples,
    readiness_report,
    verify_repository_files,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = (
    ROOT
    / "references"
    / "vision"
    / "2026-09-22"
    / "public_detector_calibration_v0_1.json"
)


class PublicDetectorCalibrationManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load_manifest(MANIFEST)

    def test_manifest_locks_real_reviewed_development_sources(self):
        manifest = self.manifest
        self.assertTrue(manifest.excluded_from_formal_promotion)
        self.assertEqual(len(manifest.samples), 19)
        self.assertEqual(
            {sample.source_session for sample in manifest.samples},
            {
                "66fe863f_youjin100",
                "b3892b34_zimo68",
                "eight_hand_match_a_hand7",
                "eight_hand_match_a_hand4",
                "special_14_match",
            },
        )

    def test_manifest_has_five_discard_and_eight_meld_calibration_frames(self):
        report = readiness_report(self.manifest)
        self.assertEqual(report["by_target"]["discard"], 5)
        self.assertEqual(report["by_target"]["meld"], 8)
        self.assertEqual(report["by_target"]["hand_reference"], 3)
        self.assertEqual(report["by_target"]["youjin_state"], 1)
        self.assertEqual(report["by_target"]["settlement"], 2)
        self.assertEqual(report["source_sessions_by_target"]["discard"], 2)
        self.assertEqual(report["source_sessions_by_target"]["meld"], 2)
        self.assertEqual(report["by_context_scope"], {
            "full_frame": 16,
            "identity_crop": 3,
        })

    def test_ten_full_frame_detector_targets_have_reviewed_bboxes(self):
        pending = pending_bbox_samples(self.manifest)
        self.assertEqual(pending, ())
        reviewed = [
            sample
            for sample in self.manifest.samples
            if (
                sample.target in {"discard", "meld"}
                and sample.context_scope == "full_frame"
            )
        ]
        self.assertEqual(len(reviewed), 10)
        self.assertTrue(all(sample.bbox is not None for sample in reviewed))
        self.assertTrue(all(sample.status == "bbox_reviewed" for sample in reviewed))
        report = readiness_report(self.manifest)
        self.assertEqual(report["bbox_ready_by_target"]["discard"], 5)
        self.assertEqual(report["bbox_ready_by_target"]["meld"], 5)
        self.assertTrue(report["public_tile_detector_bbox_ready"])

    def test_identity_crops_are_not_detector_context(self):
        crops = [
            sample for sample in self.manifest.samples
            if sample.context_scope == "identity_crop"
        ]
        self.assertEqual(len(crops), 3)
        self.assertTrue(all(sample.target == "meld" for sample in crops))
        self.assertTrue(all(sample.status == "bbox_reviewed" for sample in crops))

    def test_real_committed_evidence_files_match_locked_hashes(self):
        self.assertEqual(
            verify_repository_files(self.manifest, ROOT),
            (),
        )

    def test_bbox_template_is_empty_after_review_completion(self):
        template = bbox_review_template(self.manifest)
        self.assertEqual(
            template["schema_version"],
            "public_detector_bbox_review_v0_1",
        )
        self.assertEqual(template["samples"], [])

    def test_bbox_reviewed_status_requires_real_box(self):
        sample = self.manifest.samples[0]
        with self.assertRaises(ValueError):
            CalibrationSample(
                sample_id="invalid_review",
                source_session=sample.source_session,
                source_sha256=sample.source_sha256,
                image_path=sample.image_path,
                image_sha256=sample.image_sha256,
                frame_index=sample.frame_index,
                time_ms=sample.time_ms,
                actor=sample.actor,
                target=sample.target,
                expected_tile=sample.expected_tile,
                expected_tiles=sample.expected_tiles,
                bbox=None,
                status="bbox_reviewed",
                observation=sample.observation,
            )

    def test_archived_manifest_can_never_claim_formal_promotion_eligibility(self):
        report = readiness_report(self.manifest)
        self.assertFalse(report["formal_promotion_eligible"])
        self.assertIn(
            "source-disjoint",
            report["formal_promotion_reason"],
        )

    def test_discard_facts_require_known_public_tile_identity(self):
        discards = [
            sample for sample in self.manifest.samples
            if sample.target == "discard"
        ]
        self.assertEqual(
            {sample.expected_tile for sample in discards},
            {"P1", "S9", "N", "M4", "P7"},
        )

    def test_meld_facts_cover_peng_chi_and_stacked_four_face_reference(self):
        melds = [
            sample for sample in self.manifest.samples
            if sample.target == "meld"
        ]
        self.assertIn(("P1", "P1", "P1"), {sample.expected_tiles for sample in melds})
        self.assertIn(
            ("P1", "P1", "P1", "P1"),
            {sample.expected_tiles for sample in melds},
        )
        self.assertIn(("S7", "S8", "S9"), {sample.expected_tiles for sample in melds})
        self.assertIn(("M4", "M5", "M6"), {sample.expected_tiles for sample in melds})
        self.assertIn(("P6", "P7", "P8"), {sample.expected_tiles for sample in melds})
        self.assertIn(("P4", "P5", "P6"), {sample.expected_tiles for sample in melds})
        self.assertIn(("S4", "S5", "S6"), {sample.expected_tiles for sample in melds})
        self.assertIn(("S2", "S3", "S4"), {sample.expected_tiles for sample in melds})


if __name__ == "__main__":
    unittest.main()
