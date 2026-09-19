"""Minimal regression tests for the offline Tiles V0.1 pipeline."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from .extract_frames import extract_key_frames
from .evaluate_tiles import evaluate_template_dataset, summarize_predictions
from .infer_tiles import infer_screenshot
from .labels import append_label
from .postprocess import (MultiFrameVoter, ObservationConstraints,
                          TilePrediction, evaluate_temporal_stability,
                          validate_observation)
from .crop_rois import crop_regions
from .roi import ROIProfile
from .template_classifier import TemplateTileClassifier


class TilesV01Tests(unittest.TestCase):
    def test_roi_profile_rejects_unverified_crop(self) -> None:
        profile = ROIProfile(
            source_size=(100, 80),
            regions={
                "hand_region": (0, 40, 70, 40),
                "draw_region": (70, 40, 30, 40),
                "gold_region": (0, 0, 20, 20),
            },
            calibrated=False,
        )
        with self.assertRaises(ValueError):
            profile.crop(Image.new("RGB", (100, 80)), "hand_region")

    def test_calibrated_roi_crop_writes_all_three_regions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "dataset"
            frame = root / "images" / "frames" / "frame.png"
            frame.parent.mkdir(parents=True)
            Image.new("RGB", (100, 80), "white").save(frame)
            profile = ROIProfile(
                source_size=(100, 80),
                regions={
                    "hand_region": (0, 40, 70, 40),
                    "draw_region": (70, 40, 30, 40),
                    "gold_region": (0, 0, 20, 20),
                },
                calibrated=True,
                name="test",
            )
            profile_path = root / "meta" / "roi_profiles" / "test.json"
            profile.save(profile_path)
            rows = crop_regions(root, profile_path)
            self.assertEqual(len(rows), 3)
            self.assertEqual({row["region"] for row in rows}, {
                "hand_region", "draw_region", "gold_region",
            })
            self.assertTrue((root / "meta" / "roi_crops.jsonl").exists())

    def test_key_frame_extraction_writes_auditable_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.avi"
            writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"MJPG"), 10.0, (40, 30))
            for value in (20, 80, 140):
                writer.write(np.full((30, 40, 3), value, dtype=np.uint8))
            writer.release()

            records = extract_key_frames(source, root / "dataset", interval_seconds=0.2)
            self.assertGreaterEqual(len(records), 2)
            self.assertTrue((root / "dataset" / records[0]["image"]).exists())
            metadata = root / "dataset" / "meta" / "frames.jsonl"
            self.assertTrue(metadata.exists())
            self.assertIn("video_seconds", metadata.read_text(encoding="utf-8"))

    def test_template_inference_and_postprocess_constraints(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "dataset" / "images" / "rois" / "sample.png"
            source.parent.mkdir(parents=True)
            image = Image.new("RGB", (80, 40), "black")
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 0, 19, 39), fill="white")
            draw.rectangle((40, 0, 79, 19), fill="white")
            image.save(source)
            append_label(root / "dataset", image="images/rois/sample.png",
                         bbox=[0, 0, 20, 40], tile_id="M1",
                         region="hand_region")
            append_label(root / "dataset", image="images/rois/sample.png",
                         bbox=[40, 0, 40, 20], tile_id="P1",
                         region="draw_region")
            classifier = TemplateTileClassifier.from_dataset(root / "dataset")
            prediction = classifier.classify(image.crop((0, 0, 20, 40)))
            self.assertEqual(prediction.tile_id, "M1")

            result = validate_observation(
                [TilePrediction("M1", 0.95, "hand_region", (0, 0, 20, 40)) for _ in range(4)]
                + [TilePrediction("M1", 0.95, "draw_region", (0, 0, 20, 40))]
                + [TilePrediction("P1", 0.2, "gold_region", (0, 0, 20, 40))],
                ObservationConstraints(confidence_threshold=0.5),
            )
            self.assertTrue(any("M1 appears 5" in issue for issue in result.issues))
            self.assertEqual(len(result.rejected), 1)
            self.assertEqual(result.accepted[0].category, "wan")

    def test_holdout_evaluation_never_tests_on_its_own_template_group(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "dataset"
            image_dir = root / "images" / "rois"
            image_dir.mkdir(parents=True)

            for frame_name in ("frame_a", "frame_b"):
                image = Image.new("RGB", (40, 40), "black")
                draw = ImageDraw.Draw(image)
                # M1 template: vertical stroke. P1 template: horizontal stroke.
                draw.rectangle((7, 3, 11, 36), fill="white")
                draw.rectangle((23, 17, 36, 21), fill="white")
                image_path = image_dir / f"{frame_name}.png"
                image.save(image_path)
                append_label(
                    root, image=f"images/rois/{frame_name}.png",
                    bbox=[0, 0, 20, 40], tile_id="M1",
                    region="hand_region", source_frame=frame_name,
                )
                append_label(
                    root, image=f"images/rois/{frame_name}.png",
                    bbox=[20, 0, 20, 40], tile_id="P1",
                    region="hand_region", source_frame=frame_name,
                )

            report = evaluate_template_dataset(
                root, confidence_threshold=0.50)
            self.assertEqual(report["method"], "leave_source_group_out")
            self.assertEqual(report["distinct_source_groups"], 2)
            self.assertEqual(report["total_approved_labels"], 4)
            self.assertEqual(report["scorable_labels"], 4)
            self.assertEqual(report["unscorable_labels"], 0)
            self.assertEqual(report["scorable_coverage"], 1.0)
            self.assertEqual(report["exact_accuracy"], 1.0)
            self.assertEqual(report["category_accuracy"], 1.0)
            self.assertFalse(report["safe_for_executor"])
            self.assertEqual(
                {row["group"] for row in report["predictions"]},
                {"frame_a", "frame_b"},
            )

    def test_holdout_evaluation_exposes_missing_cross_group_class_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "dataset"
            image_dir = root / "images" / "rois"
            image_dir.mkdir(parents=True)
            for frame_name, tile_id in (("frame_a", "M1"), ("frame_b", "P1")):
                image = Image.new("RGB", (20, 40), "black")
                draw = ImageDraw.Draw(image)
                draw.rectangle((6, 4, 13, 35), fill="white")
                image.save(image_dir / f"{frame_name}.png")
                append_label(
                    root, image=f"images/rois/{frame_name}.png",
                    bbox=[0, 0, 20, 40], tile_id=tile_id,
                    region="hand_region", source_frame=frame_name,
                )
            report = evaluate_template_dataset(root)
            self.assertEqual(report["scorable_labels"], 0)
            self.assertEqual(report["unscorable_labels"], 2)
            self.assertEqual(report["scorable_coverage"], 0.0)
            self.assertIsNone(report["exact_accuracy"])
            self.assertEqual(len(report["unscorable"]), 2)

    def test_accuracy_summary_separates_low_confidence_acceptance(self) -> None:
        rows = [
            {
                "true_tile": "M1", "predicted_tile": "M1",
                "confidence": 0.95, "correct": True,
                "true_category": "wan", "predicted_category": "wan",
                "category_correct": True, "region": "hand_region",
            },
            {
                "true_tile": "P1", "predicted_tile": "P2",
                "confidence": 0.40, "correct": False,
                "true_category": "tong", "predicted_category": "tong",
                "category_correct": True, "region": "draw_region",
            },
        ]
        report = summarize_predictions(
            rows, total_labels=2, confidence_threshold=0.80)
        self.assertEqual(report["exact_accuracy"], 0.5)
        self.assertEqual(report["category_accuracy"], 1.0)
        self.assertEqual(report["accepted_labels"], 1)
        self.assertEqual(report["accepted_accuracy"], 1.0)
        self.assertEqual(report["accepted_fraction_of_scorable"], 0.5)

    def test_multiframe_voting_prefers_repeat_observation(self) -> None:
        voter = MultiFrameVoter()
        voted = voter.vote([
            [TilePrediction("M1", 0.8, "hand_region", (0, 0, 20, 40), slot=0)],
            [TilePrediction("M1", 0.9, "hand_region", (0, 0, 20, 40), slot=0)],
            [TilePrediction("P1", 0.95, "hand_region", (0, 0, 20, 40), slot=0)],
        ])
        self.assertEqual(voted[0].tile_id, "M1")
        self.assertAlmostEqual(voted[0].confidence, 0.85)

    def test_temporal_stability_reports_agreement_without_calling_it_accuracy(self) -> None:
        frames = [
            [
                TilePrediction("M1", 0.90, "hand_region", (0, 0, 20, 40), slot=0),
                TilePrediction("P1", 0.90, "hand_region", (20, 0, 20, 40), slot=1),
            ],
            [
                TilePrediction("M1", 0.80, "hand_region", (0, 0, 20, 40), slot=0),
                TilePrediction("P2", 0.95, "hand_region", (20, 0, 20, 40), slot=1),
            ],
            [
                TilePrediction("M1", 0.85, "hand_region", (0, 0, 20, 40), slot=0),
                TilePrediction("P1", 0.88, "hand_region", (20, 0, 20, 40), slot=1),
            ],
            [
                TilePrediction("M1", 0.92, "hand_region", (0, 0, 20, 40), slot=0),
                TilePrediction("P2", 0.91, "hand_region", (20, 0, 20, 40), slot=1),
            ],
        ]
        report = evaluate_temporal_stability(
            frames, minimum_agreement=0.75, minimum_frames=3)
        self.assertEqual(report.total_slots, 2)
        self.assertEqual(report.stable_slots, 1)
        self.assertEqual(report.stable_fraction, 0.5)
        first, second = report.slots
        self.assertEqual(first.voted_tile, "M1")
        self.assertEqual(first.agreement, 1.0)
        self.assertTrue(first.stable)
        self.assertEqual(second.agreement, 0.5)
        self.assertFalse(second.stable)
        self.assertFalse(report.safe_for_executor)

    def test_temporal_stability_requires_aligned_unique_slots(self) -> None:
        with self.assertRaisesRegex(ValueError, "explicit aligned slot"):
            evaluate_temporal_stability([
                [TilePrediction(
                    "M1", 0.9, "hand_region", (0, 0, 20, 40))]
            ])
        duplicate = TilePrediction(
            "M1", 0.9, "hand_region", (0, 0, 20, 40), slot=0)
        with self.assertRaisesRegex(ValueError, "duplicate prediction"):
            evaluate_temporal_stability([[duplicate, duplicate]])
        with self.assertRaises(ValueError):
            evaluate_temporal_stability([], minimum_agreement=1.1)
        with self.assertRaises(ValueError):
            evaluate_temporal_stability([], minimum_frames=0)

    def test_infer_screenshot_is_offline_and_never_executor_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "dataset"
            source = root / "images" / "frames" / "screen.png"
            source.parent.mkdir(parents=True)
            image = Image.new("RGB", (100, 60), "black")
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 0, 24, 59), fill="white")
            draw.rectangle((75, 0, 99, 29), fill="white")
            image.save(source)
            append_label(root, image="images/frames/screen.png",
                         bbox=[0, 0, 25, 60], tile_id="M1",
                         region="hand_region")
            append_label(root, image="images/frames/screen.png",
                         bbox=[75, 0, 25, 30], tile_id="P1",
                         region="gold_region")
            profile = ROIProfile(
                source_size=(100, 60),
                regions={"hand_region": (0, 0, 25, 60), "draw_region": (25, 0, 25, 60), "gold_region": (75, 0, 25, 30)},
                slots={
                    "hand_region": [(0, 0, 25, 60)],
                    "draw_region": [(0, 0, 25, 60)],
                    "gold_region": [(0, 0, 25, 30)],
                },
                calibrated=True,
            )
            profile_path = root / "meta" / "roi_profiles" / "test.json"
            profile.save(profile_path)
            result = infer_screenshot(source, root, profile_path)
            self.assertFalse(result["safe_for_executor"])
            self.assertIn("predictions", result)
            self.assertIn("category", result["predictions"][0])


if __name__ == "__main__":
    unittest.main()
