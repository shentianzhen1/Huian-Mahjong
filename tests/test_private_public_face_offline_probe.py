"""Synthetic privacy and original-match tests; NEVER commit the private 36 crops."""
from __future__ import annotations

from io import BytesIO
import hashlib
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

VISION = all(
    importlib.util.find_spec(name) is not None
    for name in ("cv2", "PIL", "numpy")
)


@unittest.skipUnless(VISION, "Vision extras optional for core tests")
class PrivatePublicFaceOfflineProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import workspace.vision.private_public_face_offline_probe as probe
        cls.probe = probe

    def setUp(self):
        from PIL import Image, ImageDraw
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.archive = self.root / "approved.zip"
        self.declaration = self.root / "external_declaration.json"
        self.sheet = b"synthetic approved reviewed sheet, not a user image"
        self.images = {}
        groups = []
        for group_num, (clip, match, ids) in enumerate((
            ("match_a.mp4", "same_original_match_a", ("P4", "P5", "P6")),
            ("match_b.mp4", "distinct_original_match_b", ("P4", "S2", "S3")),
        ), 1):
            faces = []
            for index, tile in enumerate(ids, 1):
                image = Image.new("RGB", (44, 74), (239, 239, 226))
                pen = ImageDraw.Draw(image)
                pen.rectangle(
                    (10 + index, 18, 22 + index, 42),
                    fill=(14 + index * 30, 48, 55),
                )
                buf = BytesIO()
                image.save(buf, format="PNG")
                key = f"sample_{group_num}_{index}.png"
                self.images[key] = buf.getvalue()
                faces.append({
                    "face_index": index, "crop_file": key,
                    "crop_sha256": hashlib.sha256(
                        self.images[key]
                    ).hexdigest(),
                    "bbox": [(index - 1) * 44, 402, 44, 74],
                    "approved_tile_id": tile,
                    "confirmation_status":
                        "user_confirmed_from_visual_review_sheet",
                    "formal_promotion_evidence": False,
                    "safe_for_runtime_identity": False,
                    "safe_for_executor": False,
                })
            groups.append({
                "group_id": f"G{group_num:02d}",
                "match_group": match, "clip": clip,
                "video_sha256": f"{group_num}" * 64,
                "timestamp_seconds": 1.0,
                "frame_index": 30,
                "group_bbox": [0, 402, 132, 74],
                "faces": faces, "action_kind": "UNKNOWN",
                "actor": "UNKNOWN",
            })
        self.approved = {
            "schema_version":
                "private_existing_user_confirmed_public_faces_v0_1",
            "review_sheet_sha256": hashlib.sha256(self.sheet).hexdigest(),
            "source_packet_sha256": "f" * 64,
            "development_only": True, "independent_blind_review": False,
            "source_disjoint_holdout": False,
            "formal_promotion_evidence": False,
            "safe_for_runtime": False, "safe_for_executor": False,
            "action_kind": "UNKNOWN", "actor": "UNKNOWN",
            "groups": groups, "approved_group_count": 2,
            "approved_face_count": 6, "match_group_count": 2,
        }
        self.decl = {
            "schema_version":
                "private_meld_review_user_confirmation_v0_1",
            "review_sheet_sha256": hashlib.sha256(self.sheet).hexdigest(),
            "source_packet_sha256": "f" * 64,
            "confirmed_group_ids": ["G01", "G02"],
            "user_explicitly_confirmed_all": True,
        }
        self._write()

    def _write(self, extras=None):
        self.declaration.write_text(
            json.dumps(self.decl), encoding="utf-8"
        )
        with ZipFile(self.archive, "w") as z:
            z.writestr(
                "private_approved_labels.json",
                json.dumps(self.approved),
            )
            z.writestr(
                "private_cross_match_baseline.json",
                json.dumps({"development_only": True}),
            )
            z.writestr(
                "private_user_declaration.json",
                json.dumps(self.decl),
            )
            z.writestr("reviewed_visual_sheet.jpg", self.sheet)
            z.writestr("README.txt", "synthetic")
            for filename, png in self.images.items():
                z.writestr("approved_faces/" + filename, png)
            for filename, value in (extras or {}).items():
                z.writestr(filename, value)

    def _load(self):
        with patch.object(
            self.probe, "_check_source_crops", return_value=(2, 6)
        ) as verified:
            result = self.probe.load_confirmed_private_faces(
                self.archive, self.declaration, self.root,
            )
            self.assertEqual(verified.call_count, 1)
        return result

    def test_valid_user_binding_keeps_all_labels_private(self):
        labels, clips, matches = self._load()
        self.assertEqual((len(labels), clips, matches), (6, 2, 2))
        self.assertEqual(
            {x["tile_id"] for x in labels},
            {"P4", "P5", "P6", "S2", "S3"},
        )

    def test_changed_user_sheet_and_runtime_promotion_rejected(self):
        self.decl["review_sheet_sha256"] = "0" * 64
        self.declaration.write_text(json.dumps(self.decl), "utf-8")
        with self.assertRaisesRegex(ValueError, "invalid private approval"):
            self.probe.load_confirmed_private_faces(
                self.archive, self.declaration, self.root,
            )
        self.decl["review_sheet_sha256"] = hashlib.sha256(self.sheet).hexdigest()
        self.approved["safe_for_runtime"] = True
        self._write()
        with self.assertRaisesRegex(ValueError, "unsafe label promotion"):
            self.probe.load_confirmed_private_faces(
                self.archive, self.declaration, self.root,
            )

    def test_crop_tamper_and_zip_traversal_rejected(self):
        self.images["sample_1_1.png"] = b"tampered"
        self._write()
        with self.assertRaisesRegex(ValueError, "face SHA mismatch"):
            self.probe.load_confirmed_private_faces(
                self.archive, self.declaration, self.root,
            )
        self.images["sample_1_1.png"] = self.images["sample_1_2.png"]
        self.approved["groups"][0]["faces"][0]["crop_sha256"] = hashlib.sha256(
            self.images["sample_1_1.png"]
        ).hexdigest()
        self._write(extras={"../leaked.png": b"secret"})
        with self.assertRaisesRegex(ValueError, "unreferenced"):
            self.probe.load_confirmed_private_faces(
                self.archive, self.declaration, self.root,
            )

    def test_source_video_sha_fail_closed_before_decode(self):
        import cv2
        fake = self.root / "match_a.mp4"
        fake.write_bytes(b"wrong original source")
        group = self.approved["groups"][0]
        with patch.object(
            cv2, "VideoCapture",
            side_effect=AssertionError("decode called before SHA check"),
        ):
            with self.assertRaisesRegex(ValueError, "SHA mismatch"):
                self.probe._check_source_crops(
                    [group], self.root, {}
                )

    def test_duplicate_video_bytes_cannot_fake_independent_match(self):
        sha = hashlib.sha256(b"synthetic-video").hexdigest()
        (self.root / "match_a.mp4").write_bytes(b"synthetic-video")
        (self.root / "match_b.mp4").write_bytes(b"synthetic-video")
        left, right = self.approved["groups"]
        left["video_sha256"] = sha
        right["video_sha256"] = sha
        with self.assertRaisesRegex(ValueError, "distinct match"):
            self.probe._check_source_crops(
                [left, right], self.root, {}
            )

    def test_pale_face_normalizer_abstains_on_dark_crop(self):
        from PIL import Image, ImageDraw
        raw, face_hog, reason = self.probe._features(
            Image.new("RGB", (44, 73), (0, 0, 0))
        )
        self.assertIsNone(face_hog)
        self.assertEqual(reason, "no_unambiguous_pale_face")
        img = Image.new("RGB", (44, 73), (0, 40, 55))
        pen = ImageDraw.Draw(img)
        pen.rectangle((2, 12, 42, 66), fill=(236, 236, 226))
        pen.line((8, 25, 35, 51), fill=(18, 38, 43), width=4)
        baseline, aligned, status = self.probe._features(img)
        self.assertIsNotNone(baseline)
        self.assertIsNotNone(aligned)
        self.assertEqual(status, "pale_face_found")

    def test_two_original_match_diagnostic_abstains_on_missing_class(self):
        import numpy as np
        original = [
            {"clip": "a1.mp4", "match_group": "match_A", "tile_id": "P4",
             "image": 1},
            {"clip": "a2.mp4", "match_group": "match_A", "tile_id": "P4",
             "image": 2},
            {"clip": "a2.mp4", "match_group": "match_A", "tile_id": "P5",
             "image": 3},
            {"clip": "b1.mp4", "match_group": "match_B", "tile_id": "P4",
             "image": 4},
            {"clip": "b1.mp4", "match_group": "match_B", "tile_id": "S2",
             "image": 5},
        ]
        vectors = {
            1: np.array([1., 0., 0.], dtype=np.float32),
            2: np.array([.95, .05, 0.], dtype=np.float32),
            3: np.array([0., 1., 0.], dtype=np.float32),
            4: np.array([1., 0., 0.], dtype=np.float32),
            5: np.array([0., 0., 1.], dtype=np.float32),
        }
        with patch.object(
            self.probe, "_features",
            side_effect=lambda image: (
                vectors[image], vectors[image], "pale_face_found"
            ),
        ):
            result = self.probe.compare_verified_private_faces(
                original, source_clips=3, original_matches=2,
            )
        self.assertEqual(result["query_class_absent_from_gallery"], 1)
        self.assertEqual(
            result["features"]["face_hog"]["cross_original_match_true_class_ranks"],
            [1],
        )
        self.assertEqual(result["eligible_shadow_queries"], 0)
        self.assertIsNone(result["blind_accuracy"])
        self.assertEqual(result["runtime_prediction"], "UNKNOWN")
        self.assertFalse(result["safe_for_runtime"])
        self.assertFalse(result["safe_for_executor"])


if __name__ == "__main__":
    unittest.main()
