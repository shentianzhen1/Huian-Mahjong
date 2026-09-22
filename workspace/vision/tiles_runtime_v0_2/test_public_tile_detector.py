from __future__ import annotations

import unittest
from pathlib import Path

from PIL import Image

from workspace.vision.public_detector_calibration import (
    load_manifest,
    readiness_report,
    verify_repository_files,
)
from workspace.vision.public_tile_detector import (
    best_target_coverage,
    detect_public_tile_geometry,
)


ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = (
    ROOT
    / "references"
    / "vision"
    / "2026-09-22"
    / "public_detector_calibration_v0_1.json"
)


class PublicTileDetectorCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = load_manifest(MANIFEST_PATH)
        cls.samples = tuple(
            sample
            for sample in cls.manifest.samples
            if sample.target in {"discard", "meld"}
        )

    def test_reviewed_manifest_is_now_bbox_ready_and_hash_clean(self):
        report = readiness_report(self.manifest)
        self.assertTrue(report["public_tile_detector_bbox_ready"])
        self.assertEqual(report["bbox_ready_by_target"]["discard"], 5)
        self.assertEqual(report["bbox_ready_by_target"]["meld"], 5)
        self.assertEqual(
            verify_repository_files(self.manifest, ROOT),
            (),
        )
        self.assertFalse(report["formal_promotion_eligible"])

    def test_all_ten_real_targets_are_recalled_by_geometry_intake(self):
        failures = []
        for sample in self.samples:
            self.assertIsNotNone(sample.bbox, sample.sample_id)
            image = Image.open(ROOT / sample.image_path).convert("RGB")
            detection = detect_public_tile_geometry(
                image,
                frame=sample.frame_index,
                session=sample.source_session,
            )
            score, candidate = best_target_coverage(
                detection,
                sample.bbox,  # type: ignore[arg-type]
            )
            threshold = 0.75 if sample.target == "discard" else 0.90
            if score < threshold or candidate is None:
                failures.append(
                    (
                        sample.sample_id,
                        sample.target,
                        round(score, 6),
                        len(detection.candidates),
                    )
                )
            self.assertLessEqual(
                len(detection.candidates),
                30,
                f"candidate explosion: {sample.sample_id}",
            )
            report = detection.to_dict()
            self.assertFalse(report["safe_for_hint"])
            self.assertFalse(report["safe_for_executor"])

        self.assertEqual(failures, [])

    def test_reviewed_geometry_signatures_remain_distinct(self):
        expected = {
            "66fe_opponent_discard_p1_035s": "upper_protrusion",
            "66fe_opponent_discard_s9_080s": "upper_protrusion",
            "66fe_opponent_discard_n_085s": "single_face",
            "b389_opponent_discard_m4_033s": "upper_protrusion",
            "b389_opponent_discard_p7_055s": "upper_protrusion",
            "66fe_player_peng_p1_040s": "bottom_group",
            "66fe_player_added_kong_p1_070s": "bottom_group",
            "66fe_player_chi_s789_082s": "bottom_group",
            "b389_player_chi_m456_035s": "bottom_group",
            "b389_player_chi_p678_057s": "bottom_group",
        }
        for sample in self.samples:
            image = Image.open(ROOT / sample.image_path).convert("RGB")
            detection = detect_public_tile_geometry(
                image,
                frame=sample.frame_index,
                session=sample.source_session,
            )
            score, candidate = best_target_coverage(
                detection,
                sample.bbox,  # type: ignore[arg-type]
            )
            self.assertIsNotNone(candidate, sample.sample_id)
            assert candidate is not None
            self.assertGreaterEqual(score, 0.75, sample.sample_id)
            self.assertEqual(
                candidate.geometry_kind,
                expected[sample.sample_id],
                sample.sample_id,
            )

    def test_detector_never_emits_tile_identity(self):
        sample = next(
            item
            for item in self.samples
            if item.sample_id == "66fe_opponent_discard_p1_035s"
        )
        image = Image.open(ROOT / sample.image_path).convert("RGB")
        detection = detect_public_tile_geometry(image)
        self.assertTrue(detection.candidates)
        for row in detection.to_dict()["candidates"]:
            self.assertEqual(row["tile_id"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
