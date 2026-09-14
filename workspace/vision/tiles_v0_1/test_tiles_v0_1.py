"""Minimal regression tests for the offline Tiles V0.1 pipeline."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from .extract_frames import extract_key_frames
from .infer_tiles import infer_screenshot
from .labels import append_label
from .postprocess import MultiFrameVoter, ObservationConstraints, TilePrediction, validate_observation
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

    def test_multiframe_voting_prefers_repeat_observation(self) -> None:
        voter = MultiFrameVoter()
        voted = voter.vote([
            [TilePrediction("M1", 0.8, "hand_region", (0, 0, 20, 40), slot=0)],
            [TilePrediction("M1", 0.9, "hand_region", (0, 0, 20, 40), slot=0)],
            [TilePrediction("P1", 0.95, "hand_region", (0, 0, 20, 40), slot=0)],
        ])
        self.assertEqual(voted[0].tile_id, "M1")
        self.assertAlmostEqual(voted[0].confidence, 0.85)

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
