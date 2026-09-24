"""Synthetic pixel audit for PRIVATE already-recorded public meld review packets.

Tests do not publish or require any user video, room identifier or face crop.
"""
from __future__ import annotations

import hashlib
import importlib.util
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from workspace.vision.private_meld_review_audit import (
    audit_private_meld_packet, load_private_source_registry,
)

EXTRAS = all(
    importlib.util.find_spec(name) is not None
    for name in ("cv2", "numpy", "PIL")
)


@unittest.skipUnless(EXTRAS, "Vision extras are optional in core-only CI")
class PrivateMeldReviewAuditTests(unittest.TestCase):
    def setUp(self):
        import numpy as np
        from PIL import Image

        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.video = self.root / "a.mp4"
        self.video.write_bytes(b"fake preinspected MP4 bytes")
        self.sha = hashlib.sha256(self.video.read_bytes()).hexdigest()
        self.registry = self.root / "private-registry.json"
        self.registry.write_text(json.dumps({
            "schema_version": "private_meld_sources_v0_1",
            "sources": [{
                "clip": self.video.name,
                "sha256": self.sha,
                "match_group": "one_original_match",
            }],
        }), encoding="utf-8")
        frame = np.zeros((480, 1046, 3), dtype=np.uint8)
        # RGB drawn through BGR OpenCV frame, with all three faces distinct.
        frame[402:476, 96:140] = (200, 100, 20)
        frame[402:476, 140:184] = (30, 150, 220)
        frame[402:476, 184:228] = (160, 240, 80)
        self.frame = frame
        faces = []
        self.images = {}
        for index in range(3):
            x = 96 + index * 44
            rgb = frame[402:476, x:x + 44][:, :, ::-1].copy()
            buf = BytesIO()
            Image.fromarray(rgb).save(buf, format="PNG")
            name = f"sample_face_{index+1}.png"
            self.images[name] = buf.getvalue()
            faces.append({
                "index": index, "relative_crop_file": name,
                "pixel_bbox": [x, 402, 44, 74],
                "tile_id": "UNKNOWN",
                "review_status": "pending_human_adjudication",
            })
        self.manifest = {
            "schema_version": "private_existing_evidence_review_v0_1",
            "development_only": True,
            "source_disjoint_holdout": False,
            "requires_human_review": True,
            "identity_accuracy": None,
            "extracted_group_count": 1,
            "extracted_face_slots": 3,
            "groups": [{
                "clip": self.video.name,
                "source_video_sha256": self.sha,
                "match_group": "one_original_match",
                "human_approved": False,
                "formal_promotion_evidence": False,
                "tile_identity_policy": "UNKNOWN",
                "time_seconds": 2.0,
                "frame_index_approx": 60,
                "frame_resolution": [1046, 480],
                "group_pixel_bbox": [96, 402, 132, 74],
                "faces": faces,
            }],
        }
        self.archive = self.root / "private-review.zip"

    def write_packet(self, extras=None):
        with ZipFile(self.archive, "w") as z:
            z.writestr("manifest.json", json.dumps(self.manifest))
            for name, data in self.images.items():
                z.writestr(name, data)
            for name, data in (extras or {}).items():
                z.writestr(name, data)

    def capture(self):
        import cv2
        frame = self.frame.copy()

        class FakeCapture:
            def isOpened(self): return True
            def set(self, flag, value):
                return flag == cv2.CAP_PROP_POS_MSEC and value == 2000
            def read(self): return True, frame.copy()
            def get(self, flag):
                return 61 if flag == cv2.CAP_PROP_POS_FRAMES else 0
            def release(self): pass

        return FakeCapture()

    def audit(self):
        import cv2
        with patch.object(cv2, "VideoCapture", return_value=self.capture()):
            return audit_private_meld_packet(
                self.archive, self.root, self.registry
            )

    def test_good_three_faces_verified_without_identity_promotion(self):
        self.write_packet()
        r = self.audit()
        self.assertEqual(r["source_clips_verified"], 1)
        self.assertEqual(r["original_matches"], 1)
        self.assertEqual(r["source_verified_groups"], 1)
        self.assertEqual(r["source_verified_faces"], 3)
        self.assertEqual(r["approved_identities"], 0)
        self.assertFalse(r["formal_promotion_evidence"])
        self.assertFalse(r["safe_for_executor"])

    def test_modified_crop_pixel_is_rejected(self):
        from PIL import Image
        import numpy as np

        self.images["sample_face_2.png"] = self.images["sample_face_1.png"]
        self.write_packet()
        with self.assertRaisesRegex(ValueError, "crop pixels differ"):
            self.audit()

    def test_wrong_video_hash_is_rejected_before_video_decode(self):
        import cv2

        self.video.write_bytes(b"modified-video")
        self.write_packet()
        with patch.object(
            cv2, "VideoCapture",
            side_effect=AssertionError("must reject BEFORE video decode"),
        ):
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                audit_private_meld_packet(
                    self.archive, self.root, self.registry
                )

    def test_forged_approval_and_unreviewed_crop_rejected(self):
        self.manifest["groups"][0]["human_approved"] = True
        self.write_packet()
        with self.assertRaisesRegex(ValueError, "unreviewed"):
            self.audit()
        self.manifest["groups"][0]["human_approved"] = False
        self.manifest["groups"][0]["faces"][0]["tile_id"] = "M1"
        self.write_packet()
        with self.assertRaisesRegex(ValueError, "not pending"):
            self.audit()

    def test_group_count_partition_and_frame_index_fail_closed(self):
        self.manifest["groups"][0]["faces"][1]["pixel_bbox"][0] += 1
        self.write_packet()
        with self.assertRaisesRegex(ValueError, "partition"):
            self.audit()
        self.manifest["groups"][0]["faces"][1]["pixel_bbox"][0] -= 1
        self.manifest["groups"][0]["frame_index_approx"] = 40
        self.write_packet()
        with self.assertRaisesRegex(ValueError, "resolution/index"):
            self.audit()

    def test_zip_slip_unreferenced_file_and_duplicate_crop_rejected(self):
        self.write_packet(extras={"../private/leak.png": b"not an image"})
        with self.assertRaisesRegex(ValueError, "unsafe"):
            self.audit()
        self.write_packet(extras={"extra.png": self.images["sample_face_1.png"]})
        with self.assertRaisesRegex(ValueError, "unreferenced"):
            self.audit()
        self.manifest["groups"][0]["faces"][1]["relative_crop_file"] = (
            "sample_face_1.png"
        )
        self.write_packet()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.audit()

    def test_different_clips_cannot_fake_distinct_original_match(self):
        payload = json.loads(self.registry.read_text())
        payload["sources"].append({
            "clip": "another.mp4", "sha256": self.sha,
            "match_group": "fake_independent_match",
        })
        self.registry.write_text(json.dumps(payload))
        with self.assertRaisesRegex(ValueError, "different matches"):
            load_private_source_registry(self.registry)

    def test_registry_mismatch_is_rejected_before_decode(self):
        self.manifest["groups"][0]["match_group"] = "fake_independent_match"
        self.write_packet()
        with self.assertRaisesRegex(ValueError, "source SHA/match"):
            self.audit()


if __name__ == "__main__":
    unittest.main()
