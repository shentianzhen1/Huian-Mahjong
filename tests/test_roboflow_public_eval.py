"""Offline integrity and fake-model tests; NEVER need a Roboflow API key."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from workspace.vision.roboflow_public_eval import (
    _labeled_images,
    _parse_prediction,
    box_iou,
    map_class,
    run_reviewed_trial,
    score_partial_labels,
    safe_http_status,
)

REPOSITORY = Path(__file__).resolve().parents[1]
MANIFEST = "references/vision/2026-09-22/public_identity_labels_v0_1.json"


def fixture(root: Path, tile: str = "M7") -> Path:
    image = root / "references/gameplay/trial.png"
    image.parent.mkdir(parents=True, exist_ok=True)
    # Offline manifest/sha tests intentionally need no image decoder.
    image.write_bytes(b"synthetic offline test image")
    data = {
        "schema_version": "public_identity_labels_v0_1",
        "excluded_from_formal_promotion": True,
        "development_only_reason": "synthetic test",
        "labels": [{
            "label_id": "synthetic_1",
            "source_calibration_sample_id": "synthetic_1",
            "source_session": "test_match_001",
            "source_sha256": "a" * 64,
            "image_path": "references/gameplay/trial.png",
            "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
            "frame_index": 0, "time_ms": 0,
            "region": "public_single", "tile_id": tile,
            "bbox": [0.1, 0.1, 0.2, 0.2],
            "status": "approved", "annotator": "test",
        }],
    }
    out = root / "labels.json"
    out.write_text(json.dumps(data), encoding="utf-8")
    return out


class PublicRoboflowTrialTests(unittest.TestCase):
    def test_repository_approved_public_images_hash_match(self):
        groups = _labeled_images(REPOSITORY, REPOSITORY / MANIFEST)
        self.assertEqual(sum(len(g["labels"]) for g in groups.values()), 17)
        self.assertEqual(len(groups), 9)
        self.assertEqual(len({g["source_group"] for g in groups.values()}), 2)

    def test_offline_reports_zero_calls_and_no_accuracy(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = run_reviewed_trial(root, fixture(root))
            self.assertEqual(report["mode"], "offline_integrity_only")
            self.assertEqual(report["approved_face_labels"], 1)
            self.assertEqual(report["model_calls"], 0)
            self.assertIsNone(report["approved_box_tile_recall"])
            self.assertIsNone(report["overall_detection_precision"])
            self.assertFalse(report["runtime_identity_ready"])
            self.assertFalse(report["safe_for_executor"])
            self.assertFalse(report["source_disjoint_blind_holdout"])

    def test_tampered_source_is_rejected_before_inference(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = fixture(root)
            (root / "references/gameplay/trial.png").write_bytes(b"tampered")
            called = []
            with self.assertRaisesRegex(ValueError, "SHA256"):
                run_reviewed_trial(root, manifest, infer=lambda p: called.append(p))
            self.assertEqual(called, [])

    def test_sanitized_http_status_never_exposes_exception_message(self):
        class SecretBearingError(Exception):
            def __init__(self, status_code):
                super().__init__("Do not log sensitive URL or request data")
                self.status_code = status_code
        self.assertEqual(safe_http_status(SecretBearingError(403)), "403")
        self.assertEqual(safe_http_status(SecretBearingError(404)), "404")
        self.assertEqual(safe_http_status(SecretBearingError("secret")), "unknown")
        self.assertEqual(safe_http_status(SecretBearingError(200)), "unknown")

    def test_source_taxonomy_preserves_special_unknown(self):
        self.assertEqual(map_class("1B"), "S1")
        self.assertEqual(map_class("1C"), "M1")
        self.assertEqual(map_class("9D"), "P9")
        self.assertEqual(map_class("SW"), "SOUTH")
        self.assertEqual(map_class("WD"), "B")
        self.assertIsNone(map_class("1S"))
        self.assertIsNone(map_class("4F"))
        self.assertIsNone(map_class("unknown"))

    def test_bbox_iou_and_scoring_no_double_match(self):
        labels = [
            {"tile_id": "M7", "bbox": [0.1, 0.1, 0.2, 0.2]},
            {"tile_id": "P1", "bbox": [0.6, 0.6, 0.2, 0.2]},
        ]
        predictions = [
            {"tile_id": "M7", "bbox": [0.1, 0.1, 0.2, 0.2]},
            {"tile_id": None, "bbox": [0.6, 0.6, 0.2, 0.2]},
        ]
        self.assertAlmostEqual(box_iou(labels[0]["bbox"], predictions[0]["bbox"]), 1)
        score = score_partial_labels(labels, predictions)
        self.assertEqual(score, {
            "correct_tile": 1, "wrong_or_unmapped_tile": 1, "missed_box": 0,
        })
        score = score_partial_labels(labels, predictions[:1])
        self.assertEqual(score["missed_box"], 1)

    def test_normalization_rejects_invalid_model_geometry(self):
        pred = {"class": "7C", "x": 20, "y": 20,
                "width": 10, "height": 10, "confidence": 0.85}
        self.assertEqual(_parse_prediction(pred, (100, 100))["tile_id"], "M7")
        with self.assertRaisesRegex(ValueError, "invalid model"):
            _parse_prediction({**pred, "confidence": 1.5}, (100, 100))
        with self.assertRaisesRegex(ValueError, "invalid model"):
            _parse_prediction({**pred, "x": 150}, (100, 100))

    def test_fake_online_exact_box_when_pillow_available(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is optional in core CI")
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = fixture(root)
            path = root / "references/gameplay/trial.png"
            Image.new("RGB", (100, 100), "white").save(path)
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["labels"][0]["image_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest.write_text(json.dumps(data), encoding="utf-8")
            calls = []
            def infer(image_path: str):
                calls.append(Path(image_path).is_file())
                return {"image": {"width": 100, "height": 100},
                        "predictions": [{"class": "7C", "x": 20, "y": 20,
                                         "width": 20, "height": 20,
                                         "confidence": 0.91}]}
            report = run_reviewed_trial(root, manifest, infer=infer)
            self.assertEqual(calls, [True])
            self.assertEqual(report["correct_tile"], 1)
            self.assertEqual(report["wrong_or_unmapped_tile"], 0)
            self.assertEqual(report["approved_box_tile_recall"], 1.0)
            self.assertIsNone(report["overall_detection_precision"])


if __name__ == "__main__":
    unittest.main()
