"""Minimal regression tests for the offline Tiles V0.1 pipeline."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from .extract_frames import extract_key_frames
from .audit_labels import audit_labels
from .dataset_status import dataset_readiness
from .evaluate_tiles import evaluate_template_dataset, summarize_predictions
from .infer_tiles import infer_screenshot
from .labels import append_label
from .gold_classifier import count_tong_pips
from .mine_stability_sequences import mine_presence_sequences
from .postprocess import (MultiFrameVoter, ObservationConstraints,
                          TilePrediction, evaluate_temporal_stability,
                          validate_observation)
from .public_state import (
    HuianPublicStateProfile, PublicStateCandidate, PublicStateObservation,
    fuse_public_state,
)
from .public_state_scores import (
    ScorePairRead, decode_score_candidates, prepare_score_crop,
    prepare_score_gray, read_score_pair,
)
from .public_state_status import (
    StatusLineRead, TesseractStatusReader,
    infer_missing_hand_from_transition, parse_hand_progress,
    parse_remaining_tiles, prepare_status_crop,
)
from .public_state_reader import compose_public_candidate
from .crop_rois import crop_regions
from .roi import ROIProfile
from .template_classifier import (
    TemplateTileClassifier, _normalize_gold_face,
    _normalize_tile_face, _tile_face_box
)


class TilesV01Tests(unittest.TestCase):
    def test_runtime_v02_tile_crop_uses_root_labels_and_source_bbox(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "dataset"
            template_dir = root / "templates" / "hand"
            template_dir.mkdir(parents=True)
            tile = Image.new("RGB", (40, 64), "white")
            ImageDraw.Draw(tile).rectangle((16, 8, 23, 55), fill="black")
            tile.save(template_dir / "m1.png")
            tile_b = Image.new("RGB", (42, 66), "white")
            ImageDraw.Draw(tile_b).rectangle((17, 9, 24, 57), fill="black")
            tile_b.save(template_dir / "m1_b.png")
            row = {
                "image": "templates/hand/m1.png",
                "source_id": "src_anonymous",
                "source_session": "session_anonymous",
                "source_frame": 123,
                "bbox": [600, 400, 40, 64],
                "slot": 0,
                "tile_id": "M1",
                "region": "hand_region",
                "approved": True,
                "status": "approved",
                "sha256": "0" * 64,
            }
            row_b = {
                **row,
                "id": "runtime_b",
                "image": "templates/hand/m1_b.png",
                "source_session": "session_b",
                "source_frame": 456,
                "bbox": [500, 300, 42, 66],
                "sha256": "1" * 64,
            }
            (root / "labels.jsonl").write_text(
                json.dumps(row) + "\n" + json.dumps(row_b) + "\n",
                encoding="utf-8",
            )

            classifier = TemplateTileClassifier.from_dataset(root)

            self.assertEqual(sorted(classifier.templates), ["M1"])
            self.assertEqual(
                classifier.classify(tile, region="hand_region").tile_id,
                "M1",
            )
            report = evaluate_template_dataset(root)
            self.assertEqual(report["scorable_labels"], 2)
            self.assertEqual(report["exact_accuracy"], 1.0)

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

    def test_template_normalization_crops_dark_ui_margins(self) -> None:
        tile = Image.new("RGB", (24, 40), "white")
        draw = ImageDraw.Draw(tile)
        draw.rectangle((9, 5, 14, 35), fill="black")

        framed = Image.new("RGB", (40, 60), (0, 45, 45))
        framed.paste(tile, (8, 10))
        normalized = _normalize_tile_face(framed)

        self.assertLess(normalized.width, framed.width)
        self.assertLess(normalized.height, framed.height)
        self.assertGreaterEqual(normalized.width, 20)
        self.assertGreaterEqual(normalized.height, 36)


    def test_gold_skin_normalization_trims_outer_rim(self) -> None:
        image = Image.new("RGB", (50, 70), (90, 20, 20))
        draw = ImageDraw.Draw(image)
        draw.rectangle((4, 3, 45, 65), fill=(215, 185, 75))
        draw.rectangle((18, 15, 23, 55), fill="black")
        normalized = _normalize_gold_face(image)
        self.assertLess(normalized.width, image.width)
        self.assertLess(normalized.height, image.height)
        self.assertGreater(normalized.width, 30)
        self.assertGreater(normalized.height, 50)

    def test_gold_badge_does_not_override_base_tile_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "dataset"
            image_dir = root / "images" / "rois"
            image_dir.mkdir(parents=True)

            def gold_tile(path, horizontal=False, badge_fill="red"):
                image = Image.new("RGB", (50, 70), (80, 15, 15))
                draw = ImageDraw.Draw(image)
                draw.rectangle((4, 3, 45, 65), fill=(215, 185, 75))
                if horizontal:
                    draw.rectangle((10, 32, 38, 38), fill="black")
                else:
                    draw.rectangle((22, 12, 28, 56), fill="black")
                draw.rectangle((35, 5, 46, 18), fill=badge_fill)
                image.save(path)
                return image

            gold_tile(image_dir / "m1.png", horizontal=False)
            gold_tile(image_dir / "p1.png", horizontal=True)
            append_label(
                root, image="images/rois/m1.png",
                bbox=[0, 0, 50, 70], tile_id="M1",
                region="gold_region", source_session="seed_a",
            )
            append_label(
                root, image="images/rois/p1.png",
                bbox=[0, 0, 50, 70], tile_id="P1",
                region="gold_region", source_session="seed_b",
            )
            classifier = TemplateTileClassifier.from_dataset(root)

            query = gold_tile(
                image_dir / "query.png",
                horizontal=False, badge_fill="blue"
            )
            prediction = classifier.classify(
                query, region="gold_region"
            )
            self.assertEqual(prediction.tile_id, "M1")

    def test_gold_tong_pip_counter_ignores_top_right_badge(self) -> None:
        base = Image.new("RGB", (44, 64), (222, 205, 102))
        draw = ImageDraw.Draw(base)
        for cx, cy in ((13, 22), (31, 22), (13, 46), (31, 46)):
            draw.ellipse((cx - 5, cy - 5, cx + 5, cy + 5),
                         outline=(0, 90, 70), width=2)
            draw.ellipse((cx - 2, cy - 2, cx + 2, cy + 2),
                         fill=(0, 70, 60))

        # This synthetic shape only checks badge isolation. Exact Hough recall is
        # calibrated on reviewed replay frames, not on hand-drawn circles.
        baseline = count_tong_pips(base)
        self.assertGreater(baseline, 0)

        with_badge = base.copy()
        badge = ImageDraw.Draw(with_badge)
        badge.rectangle((31, 0, 43, 17), fill=(230, 150, 30))
        badge.line((33, 2, 42, 15), fill=(130, 60, 20), width=2)
        self.assertEqual(count_tong_pips(with_badge), baseline)

    def test_tile_face_presence_rejects_empty_dark_slot(self) -> None:
        empty = Image.new("RGB", (44, 68), (0, 45, 45))
        self.assertIsNone(_tile_face_box(empty))

        occupied = Image.new("RGB", (44, 68), (0, 45, 45))
        draw = ImageDraw.Draw(occupied)
        draw.rectangle((5, 3, 38, 65), fill="white")
        draw.rectangle((18, 12, 24, 52), fill="black")
        self.assertIsNotNone(_tile_face_box(occupied))

    def test_classifier_skips_empty_slot_instead_of_inventing_tile(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "dataset"
            image_dir = root / "images" / "rois"
            image_dir.mkdir(parents=True)

            template = Image.new("RGB", (20, 40), "white")
            template_draw = ImageDraw.Draw(template)
            template_draw.rectangle((7, 4, 12, 35), fill="black")
            template.save(image_dir / "template.png")
            append_label(
                root, image="images/rois/template.png",
                bbox=[0, 0, 20, 40], tile_id="M1",
                region="hand_region", source_session="template_session",
            )
            classifier = TemplateTileClassifier.from_dataset(root)

            frame = Image.new("RGB", (80, 60), (0, 45, 45))
            frame_draw = ImageDraw.Draw(frame)
            frame_draw.rectangle((3, 7, 22, 46), fill="white")
            frame_draw.rectangle((10, 11, 15, 41), fill="black")
            profile = ROIProfile(
                source_size=(80, 60),
                regions={
                    "hand_region": (0, 0, 25, 50),
                    "draw_region": (25, 0, 25, 50),
                    "gold_region": (50, 0, 25, 50),
                },
                slots={
                    "hand_region": [(0, 0, 25, 50)],
                    "draw_region": [(0, 0, 25, 50)],
                    "gold_region": [(0, 0, 25, 50)],
                },
                calibrated=True,
            )
            self.assertEqual(
                len(classifier.classify_slots(frame, profile, "hand_region")), 1
            )
            self.assertEqual(
                classifier.classify_slots(frame, profile, "draw_region"), ()
            )
            self.assertEqual(
                classifier.classify_slots(frame, profile, "gold_region"), ()
            )


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

    def test_operational_classifier_uses_same_region_templates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "dataset"
            image_dir = root / "images" / "rois"
            image_dir.mkdir(parents=True)
            sample = Image.new("RGB", (20, 40), "white")
            draw = ImageDraw.Draw(sample)
            draw.rectangle((7, 4, 12, 35), fill="black")
            sample.save(image_dir / "same.png")

            append_label(
                root, image="images/rois/same.png",
                bbox=[0, 0, 20, 40], tile_id="M1",
                region="hand_region", source_session="hand_source",
            )
            append_label(
                root, image="images/rois/same.png",
                bbox=[0, 0, 20, 40], tile_id="P1",
                region="draw_region", source_session="draw_source",
            )
            classifier = TemplateTileClassifier.from_dataset(root)
            self.assertEqual(
                classifier.classify(sample, region="hand_region").tile_id,
                "M1",
            )
            self.assertEqual(
                classifier.classify(sample, region="draw_region").tile_id,
                "P1",
            )

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
            self.assertEqual(report["method"], "leave_source_session_or_group_out")
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

    def test_holdout_prefers_source_session_over_individual_frames(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "dataset"
            image_dir = root / "images" / "rois"
            image_dir.mkdir(parents=True)

            samples = (
                ("a1", "session_a", "M1"),
                ("a2", "session_a", "M1"),
                ("b1", "session_b", "M1"),
            )
            for name, session, tile_id in samples:
                image = Image.new("RGB", (20, 40), "black")
                draw = ImageDraw.Draw(image)
                draw.rectangle((6, 4, 13, 35), fill="white")
                image.save(image_dir / f"{name}.png")
                append_label(
                    root, image=f"images/rois/{name}.png",
                    bbox=[0, 0, 20, 40], tile_id=tile_id,
                    region="hand_region", source_frame=name,
                    source_session=session,
                )

            report = evaluate_template_dataset(root, confidence_threshold=0.50)
            self.assertEqual(report["distinct_source_groups"], 2)
            self.assertEqual(
                {row["group"] for row in report["predictions"]},
                {"session_a", "session_b"},
            )
            readiness = dataset_readiness(root)
            self.assertEqual(readiness["source_groups"], 2)
            self.assertEqual(
                readiness["class_source_group_counts"]["M1"], 2
            )

    def test_same_region_holdout_does_not_cross_ui_render_domains(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "dataset"
            image_dir = root / "images" / "rois"
            image_dir.mkdir(parents=True)
            for frame_name, region in (
                    ("frame_a", "hand_region"), ("frame_b", "draw_region")):
                image = Image.new("RGB", (20, 40), "black")
                draw = ImageDraw.Draw(image)
                draw.rectangle((6, 4, 13, 35), fill="white")
                image.save(image_dir / f"{frame_name}.png")
                append_label(
                    root, image=f"images/rois/{frame_name}.png",
                    bbox=[0, 0, 20, 40], tile_id="M1",
                    region=region, source_frame=frame_name,
                )

            cross_region = evaluate_template_dataset(root)
            self.assertEqual(cross_region["scorable_labels"], 2)
            self.assertEqual(cross_region["template_scope"], "all_regions")

            same_region = evaluate_template_dataset(
                root, template_scope="same_region")
            self.assertEqual(
                same_region["method"], "leave_source_session_or_group_out_same_region")
            self.assertEqual(same_region["template_scope"], "same_region")
            self.assertEqual(same_region["scorable_labels"], 0)
            self.assertEqual(same_region["unscorable_labels"], 2)
            self.assertTrue(all(
                row["reason"] ==
                "true_class_missing_outside_holdout_group_in_region"
                for row in same_region["unscorable"]
            ))

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

    def test_dataset_readiness_prioritizes_cross_frame_replication(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "dataset"
            image_dir = root / "images" / "rois"
            image_dir.mkdir(parents=True)
            for name in ("a", "b", "c"):
                Image.new("RGB", (20, 40), "white").save(
                    image_dir / f"{name}.png")

            append_label(
                root, image="images/rois/a.png", bbox=[0, 0, 20, 40],
                tile_id="M1", region="hand_region", source_frame="a")
            append_label(
                root, image="images/rois/b.png", bbox=[0, 0, 20, 40],
                tile_id="M1", region="draw_region", source_frame="b")
            append_label(
                root, image="images/rois/c.png", bbox=[0, 0, 20, 40],
                tile_id="P1", region="gold_region", source_frame="c")

            report = dataset_readiness(root)
            self.assertEqual(report["approved_labels"], 3)
            self.assertEqual(report["source_groups"], 3)
            self.assertEqual(report["replicated_classes"], ["M1"])
            self.assertEqual(report["single_group_classes"], ["P1"])
            self.assertEqual(report["scorable_labels_for_group_holdout"], 2)
            self.assertTrue(report["can_run_leakage_safe_accuracy"])
            self.assertTrue(report["all_three_regions_labelled"])
            self.assertFalse(report["all_observed_classes_replicated"])
            self.assertIn(
                "P1",
                report["next_data_priority"]["replicate_across_source_groups"],
            )
            self.assertFalse(report["safe_for_executor"])

    def test_label_audit_surfaces_disagreement_without_rewriting_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "dataset"
            image_dir = root / "images" / "rois"
            image_dir.mkdir(parents=True)

            def write_pattern(name, horizontal=False):
                image = Image.new("RGB", (20, 40), "white")
                draw = ImageDraw.Draw(image)
                if horizontal:
                    draw.rectangle((2, 17, 17, 22), fill="black")
                else:
                    draw.rectangle((7, 3, 12, 36), fill="black")
                image.save(image_dir / f"{name}.png")

            write_pattern("a1")
            write_pattern("b1")
            write_pattern("a2", horizontal=True)
            write_pattern("b2", horizontal=True)

            append_label(
                root, image="images/rois/a1.png",
                bbox=[0, 0, 20, 40], tile_id="M1",
                region="hand_region", source_session="a",
            )
            append_label(
                root, image="images/rois/b1.png",
                bbox=[0, 0, 20, 40], tile_id="M1",
                region="hand_region", source_session="b",
            )
            append_label(
                root, image="images/rois/a2.png",
                bbox=[0, 0, 20, 40], tile_id="P1",
                region="hand_region", source_session="a",
            )
            # Deliberately wrong reviewed label: horizontal P1-looking sample
            # is entered as M1. The audit must flag it, never auto-correct it.
            append_label(
                root, image="images/rois/b2.png",
                bbox=[0, 0, 20, 40], tile_id="M1",
                region="hand_region", source_session="b",
            )

            report = audit_labels(root, review_confidence=0.80)
            self.assertGreaterEqual(report["review_queue_size"], 1)
            self.assertGreaterEqual(report["model_disagreements"], 1)
            self.assertEqual(report["auto_corrections"], 0)
            self.assertFalse(report["safe_for_executor"])

    def test_empty_dataset_is_explicitly_not_accuracy_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report = dataset_readiness(Path(temp))
            self.assertEqual(report["approved_labels"], 0)
            self.assertEqual(report["scorable_fraction"], 0.0)
            self.assertFalse(report["can_run_leakage_safe_accuracy"])
            self.assertFalse(report["all_three_regions_labelled"])
            self.assertEqual(
                set(report["next_data_priority"]["empty_regions"]),
                {"hand_region", "draw_region", "gold_region"},
            )

    def test_presence_sequence_miner_splits_on_empty_draw_slot(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "dataset"
            template_path = root / "images" / "rois" / "template.png"
            template_path.parent.mkdir(parents=True)

            template = Image.new("RGB", (20, 40), "white")
            template_draw = ImageDraw.Draw(template)
            template_draw.rectangle((7, 4, 12, 35), fill="black")
            template.save(template_path)
            append_label(
                root, image="images/rois/template.png",
                bbox=[0, 0, 20, 40], tile_id="M1",
                region="draw_region", source_session="template",
            )

            profile = ROIProfile(
                source_size=(80, 60),
                regions={
                    "hand_region": (0, 0, 25, 50),
                    "draw_region": (25, 0, 25, 50),
                    "gold_region": (50, 0, 25, 50),
                },
                slots={
                    "hand_region": [(0, 0, 25, 50)],
                    "draw_region": [(0, 0, 25, 50)],
                    "gold_region": [(0, 0, 25, 50)],
                },
                calibrated=True,
                region_modes={"gold_region": "marker"},
            )
            profile_path = root / "meta" / "roi_profiles" / "test.json"
            profile.save(profile_path)

            video = Path(temp) / "sequence.avi"
            writer = cv2.VideoWriter(
                str(video), cv2.VideoWriter_fourcc(*"MJPG"),
                5.0, (80, 60),
            )
            for occupied in (True, True, True, False, True, True, True):
                frame = np.zeros((60, 80, 3), dtype=np.uint8)
                frame[:] = (45, 45, 0)
                if occupied:
                    cv2.rectangle(frame, (28, 4), (47, 43),
                                  (255, 255, 255), -1)
                    cv2.rectangle(frame, (35, 8), (40, 38),
                                  (0, 0, 0), -1)
                writer.write(frame)
            writer.release()

            report = mine_presence_sequences(
                video, root, profile_path,
                region="draw_region", interval_seconds=0.2,
                minimum_frames=3, minimum_similarity=0.80,
                minimum_agreement=0.80,
            )
            self.assertEqual(report["sequence_count"], 2)
            self.assertEqual(report["stable_sequence_count"], 2)
            self.assertEqual(report["stable_sequence_fraction"], 1.0)
            self.assertTrue(all(
                sequence["stability"]["stable_fraction"] == 1.0
                for sequence in report["sequences"]
            ))
            self.assertFalse(report["safe_for_executor"])

    def test_score_preprocessing_upscales_to_binary_image(self) -> None:
        source = Image.new("RGB", (20, 10), (0, 35, 35))
        draw = ImageDraw.Draw(source)
        draw.rectangle((6, 2, 12, 7), fill=(210, 210, 90))
        binary = prepare_score_crop(
            source, threshold=80, scale=4, border=3
        )
        self.assertEqual(binary.ndim, 2)
        self.assertEqual(
            set(np.unique(binary).tolist()).issubset({0, 255}), True
        )
        self.assertGreater(binary.shape[0], source.height)
        self.assertGreater(binary.shape[1], source.width)

    def test_score_gray_preprocessing_preserves_grayscale_shape(self) -> None:
        source = Image.new("RGB", (20, 10), (0, 35, 35))
        draw = ImageDraw.Draw(source)
        draw.rectangle((6, 2, 12, 7), fill=(210, 210, 90))
        gray = prepare_score_gray(source, scale=4)
        self.assertEqual(gray.ndim, 2)
        self.assertEqual(gray.shape, (40, 80))
        self.assertGreater(int(gray.max()), int(gray.min()))

    def test_score_reader_gray_first_can_infer_missing_side(self) -> None:
        class FakeOCR:
            def __init__(self, outputs):
                self.outputs = iter(outputs)

            def __call__(self, _image):
                return next(self.outputs)

        # Gray pass: top is unreadable, bottom is a clean 923.
        backend = FakeOCR(["", "923"])
        frame = Image.new("RGB", (1000, 500), "black")
        read = read_score_pair(
            frame, backend=backend, gray_first=True
        )
        self.assertEqual(read.score_pair, (1077, 923))
        self.assertEqual(read.mode, "gray_inferred_top")
        self.assertEqual(read.confidence, 0.75)
        self.assertFalse(read.safe_for_executor)

    def test_score_candidate_decoder_prefers_2000_point_pair(self) -> None:
        self.assertEqual(
            decode_score_candidates(
                (1072, 1077), (928, 923)
            ),
            (1072, 928, "direct"),
        )
        self.assertEqual(
            decode_score_candidates((1105,), ()),
            (1105, 895, "inferred_bottom"),
        )
        self.assertEqual(
            decode_score_candidates((), (923,)),
            (1077, 923, "inferred_top"),
        )
        self.assertEqual(
            decode_score_candidates((1077, 1072), (925,)),
            (None, None, "invalid"),
        )

    def test_score_reader_uses_multi_threshold_candidates_before_total_guard(self) -> None:
        class FakeOCR:
            def __init__(self, outputs):
                self.outputs = iter(outputs)

            def __call__(self, _binary):
                return next(self.outputs)

        # Three top attempts, followed by three bottom attempts.
        backend = FakeOCR([
            "1072", "1077", "1077",
            "928", "923", "923",
        ])
        frame = Image.new("RGB", (1000, 500), "black")
        read = read_score_pair(
            frame,
            backend=backend,
            thresholds=(70, 80, 90),
            source_frame="synthetic",
            gray_first=False,
        )
        self.assertEqual(read.score_pair, (1077, 923))
        self.assertEqual(read.mode, "direct")
        self.assertEqual(read.confidence, 1.0)
        self.assertFalse(read.safe_for_executor)
        self.assertEqual(read.to_candidate().score_pair, (1077, 923))

    def test_score_reader_only_infers_missing_side_from_unique_candidate(self) -> None:
        class FakeOCR:
            def __init__(self, outputs):
                self.outputs = iter(outputs)

            def __call__(self, _binary):
                return next(self.outputs)

        backend = FakeOCR([
            "1105", "1105", "1105",
            "", "", "",
        ])
        frame = Image.new("RGB", (1000, 500), "black")
        read = read_score_pair(frame, backend=backend, gray_first=False)
        self.assertEqual(read.score_pair, (1105, 895))
        self.assertEqual(read.mode, "inferred_bottom")
        self.assertEqual(read.confidence, 0.75)
        self.assertFalse(read.safe_for_executor)

    def test_status_reader_uses_tighter_remaining_crop_only_after_invalid_primary(self) -> None:
        class FakeOCR:
            def __init__(self, outputs):
                self.outputs = iter(outputs)
                self.calls = 0

            def __call__(self, _image):
                self.calls += 1
                return next(self.outputs)

        frame = Image.new("RGB", (1000, 500), "black")
        backend = FakeOCR(["985", "98", "5/8"])
        read = TesseractStatusReader(backend).read(frame)
        self.assertEqual(read.remaining_tiles, 98)
        self.assertEqual(read.remaining_mode, "right_trim_fallback")
        self.assertEqual(read.raw_remaining, "985")
        self.assertEqual(read.raw_remaining_fallback, "98")
        self.assertEqual(read.hand_number, 5)
        self.assertEqual(backend.calls, 3)
        self.assertNotIn("remaining_unreadable", read.issues)

    def test_status_reader_never_replaces_valid_primary_remaining_read(self) -> None:
        class FakeOCR:
            def __init__(self, outputs):
                self.outputs = iter(outputs)
                self.calls = 0

            def __call__(self, _image):
                self.calls += 1
                return next(self.outputs)

        frame = Image.new("RGB", (1000, 500), "black")
        backend = FakeOCR(["107", "1/8"])
        read = TesseractStatusReader(backend).read(frame)
        self.assertEqual(read.remaining_tiles, 107)
        self.assertEqual(read.remaining_mode, "primary")
        self.assertIsNone(read.raw_remaining_fallback)
        self.assertEqual(read.hand_number, 1)
        self.assertEqual(backend.calls, 2)

    def test_status_reader_corrects_target_font_seven_confusion(self) -> None:
        self.assertEqual(parse_remaining_tiles("10/"), 107)
        self.assertEqual(parse_remaining_tiles("105"), 105)
        self.assertEqual(parse_hand_progress("7/8"), 7)
        self.assertEqual(parse_hand_progress("//8"), 7)
        self.assertEqual(parse_hand_progress("5/8"), 5)
        self.assertIsNone(parse_hand_progress("0/8"))

    def test_status_preprocessing_upscales_grayscale(self) -> None:
        source = Image.new("RGB", (20, 10), (0, 35, 35))
        draw = ImageDraw.Draw(source)
        draw.rectangle((6, 2, 12, 7), fill=(210, 210, 90))
        gray = prepare_status_crop(source, scale=4)
        self.assertEqual(gray.shape, (40, 80))
        self.assertGreater(int(gray.max()), int(gray.min()))

    def test_missing_hand_can_only_advance_on_trusted_score_transition(self) -> None:
        previous = PublicStateObservation(
            980, 1020, 4, 105, 3, 3, 3, (), False
        )
        hand, inferred = infer_missing_hand_from_transition(
            None, previous=previous, current_score_pair=(1004, 996)
        )
        self.assertEqual(hand, 5)
        self.assertTrue(inferred)

        same, inferred = infer_missing_hand_from_transition(
            None, previous=previous, current_score_pair=(980, 1020)
        )
        self.assertIsNone(same)
        self.assertFalse(inferred)

    def test_unified_public_state_composes_missing_hand_from_score_transition(self) -> None:
        previous = PublicStateObservation(
            980, 1020, 4, 105, 3, 3, 3, (), False
        )
        score = ScorePairRead(
            1004, 996, "direct", (), (), 1.0,
            source_frame="hand5", safe_for_executor=False,
        )
        status = StatusLineRead(
            remaining_tiles=106,
            hand_number=None,
            raw_remaining="106",
            raw_hand_progress="0/8",
            issues=("hand_unreadable",),
            safe_for_executor=False,
        )
        candidate, issues = compose_public_candidate(
            score, status, previous=previous, source_frame="hand5"
        )
        self.assertEqual(candidate.score_pair, (1004, 996))
        self.assertEqual(candidate.hand_number, 5)
        self.assertEqual(candidate.remaining_tiles, 106)
        self.assertIn("hand_inferred_from_score_transition", issues)
        self.assertFalse(candidate.confidence == 0)

    def test_public_state_rois_scale_across_recording_sizes(self) -> None:
        profile = HuianPublicStateProfile()
        small = Image.new("RGB", (960, 448), "black")
        large = Image.new("RGB", (1046, 480), "black")
        small_crops = profile.crops(small)
        large_crops = profile.crops(large)
        self.assertEqual(set(small_crops), {
            "top_right_score", "bottom_left_score", "status_line",
            "remaining_tiles", "hand_progress",
        })
        self.assertGreater(
            large_crops["top_right_score"].width,
            small_crops["top_right_score"].width,
        )
        self.assertGreater(
            large_crops["status_line"].height,
            small_crops["status_line"].height,
        )

    def test_public_state_consensus_rejects_single_frame_score_noise(self) -> None:
        candidates = [
            PublicStateCandidate(1077, 923, 8, 105, 0.95),
            PublicStateCandidate(1077, 923, 8, 105, 0.96),
            PublicStateCandidate(1072, 928, 8, 105, 0.99),
        ]
        observed = fuse_public_state(candidates, minimum_votes=2)
        self.assertEqual(observed.score_pair, (1077, 923))
        self.assertEqual(observed.hand_number, 8)
        self.assertEqual(observed.remaining_tiles, 105)
        self.assertEqual(observed.score_votes, 2)
        self.assertTrue(observed.valid)
        self.assertFalse(observed.safe_for_executor)

    def test_public_state_discards_non_conserving_score_pairs_before_vote(self) -> None:
        candidates = [
            PublicStateCandidate(1077, 923, 8, 105),
            PublicStateCandidate(1077, 923, 8, 105),
            PublicStateCandidate(1077, 928, 8, 105),
            PublicStateCandidate(1077, 928, 8, 105),
            PublicStateCandidate(1077, 928, 8, 105),
        ]
        observed = fuse_public_state(candidates, minimum_votes=2)
        self.assertEqual(observed.score_pair, (1077, 923))
        self.assertTrue(observed.valid)

    def test_public_state_blocks_score_change_inside_same_hand(self) -> None:
        previous = PublicStateObservation(
            1077, 923, 8, 105, 3, 3, 3, (), False
        )
        candidates = [
            PublicStateCandidate(1113, 887, 8, 104),
            PublicStateCandidate(1113, 887, 8, 104),
        ]
        observed = fuse_public_state(
            candidates, previous=previous, minimum_votes=2
        )
        self.assertIn("score_changed_inside_hand", observed.issues)

    def test_public_state_allows_score_change_at_next_hand_boundary(self) -> None:
        previous = PublicStateObservation(
            1105, 895, 7, 40, 3, 3, 3, (), False
        )
        candidates = [
            PublicStateCandidate(1077, 923, 8, 108),
            PublicStateCandidate(1077, 923, 8, 108),
        ]
        observed = fuse_public_state(
            candidates, previous=previous, minimum_votes=2
        )
        self.assertEqual(observed.score_pair, (1077, 923))
        self.assertEqual(observed.hand_number, 8)
        self.assertEqual(observed.remaining_tiles, 108)
        self.assertTrue(observed.valid)

    def test_public_state_blocks_remaining_count_increase_inside_hand(self) -> None:
        previous = PublicStateObservation(
            1077, 923, 8, 80, 3, 3, 3, (), False
        )
        candidates = [
            PublicStateCandidate(1077, 923, 8, 81),
            PublicStateCandidate(1077, 923, 8, 81),
        ]
        observed = fuse_public_state(
            candidates, previous=previous, minimum_votes=2
        )
        self.assertIn("remaining_increased_inside_hand", observed.issues)

    def test_public_state_can_cross_check_engine_match_score(self) -> None:
        candidates = [
            PublicStateCandidate(1077, 923, 8, 105),
            PublicStateCandidate(1077, 923, 8, 105),
        ]
        ok = fuse_public_state(
            candidates, expected_scores=(1077, 923), minimum_votes=2
        )
        self.assertNotIn("engine_score_mismatch", ok.issues)
        mismatch = fuse_public_state(
            candidates, expected_scores=(1105, 895), minimum_votes=2
        )
        self.assertIn("engine_score_mismatch", mismatch.issues)

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
                region_modes={
                    "hand_region": "tile",
                    "draw_region": "tile",
                    "gold_region": "marker",
                },
            )
            profile_path = root / "meta" / "roi_profiles" / "test.json"
            profile.save(profile_path)
            loaded = ROIProfile.load(profile_path)
            self.assertEqual(loaded.region_mode("gold_region"), "marker")
            result = infer_screenshot(source, root, profile_path)
            self.assertFalse(result["safe_for_executor"])
            self.assertIn("predictions", result)
            self.assertIn("category", result["predictions"][0])
            self.assertIn("is_gold", result["predictions"][0])
            self.assertFalse(any(
                item["region"] == "gold_region"
                for item in result["predictions"]
            ))
            self.assertEqual(len(result["markers"]), 1)
            self.assertEqual(result["markers"][0]["region"], "gold_region")
            self.assertTrue(result["markers"][0]["present"])


if __name__ == "__main__":
    unittest.main()
