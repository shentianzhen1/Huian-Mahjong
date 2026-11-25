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
            if (
                sample.target in {"discard", "meld"}
                and sample.context_scope == "full_frame"
            )
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

    def test_high_resolution_upper_row_is_group_not_single_face(self):
        from PIL import ImageDraw

        image = Image.new("RGB", (2048, 944), (0, 80, 82))
        draw = ImageDraw.Draw(image)
        # Compact opponent-side exposed row: whole 3-face body is only about
        # 6.5% of frame width, which used to fall inside the single-face gate.
        draw.rectangle((1220, 30, 1354, 82), fill=(235, 235, 225))
        detection = detect_public_tile_geometry(image)
        upper = [
            candidate for candidate in detection.candidates
            if candidate.geometry_kind == "top_group"
        ]
        self.assertEqual(len(upper), 1)
        self.assertGreater(upper[0].pixel_bbox[2] / upper[0].pixel_bbox[3], 2.0)

    def test_high_resolution_fragmented_lower_row_regroups(self):
        from PIL import ImageDraw

        image = Image.new("RGB", (2048, 944), (0, 80, 82))
        draw = ImageDraw.Draw(image)
        # Three separated faces at 2048px width stay independent connected
        # components; the exposed-group pass must regroup them by adjacency.
        for x in (190, 248, 306):
            draw.rectangle((x, 812, x + 50, 920), fill=(235, 235, 225))
        detection = detect_public_tile_geometry(image)
        groups = [
            candidate for candidate in detection.candidates
            if candidate.geometry_kind == "bottom_group"
        ]
        self.assertEqual(len(groups), 1)
        group = groups[0]
        self.assertLess(group.pixel_bbox[0], 190)
        self.assertGreater(group.pixel_bbox[0] + group.pixel_bbox[2], 356)

    def test_high_resolution_lower_hand_zone_is_not_regrouped_as_meld(self):
        from PIL import ImageDraw

        image = Image.new("RGB", (2048, 944), (0, 80, 82))
        draw = ImageDraw.Draw(image)
        # Same geometry in the central concealed-hand zone must not become a
        # player exposed meld merely because three faces are adjacent.
        for x in (850, 908, 966):
            draw.rectangle((x, 812, x + 50, 920), fill=(235, 235, 225))
        detection = detect_public_tile_geometry(image)
        groups = [
            candidate for candidate in detection.candidates
            if candidate.geometry_kind == "bottom_group"
        ]
        self.assertEqual(groups, [])

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
