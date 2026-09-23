"""Synthetic, core-only provenance and human-approval contract tests (#69)."""
from __future__ import annotations

import hashlib
import json
import struct
import zlib
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from workspace.vision.source_river_review_audit import audit_review

SHA = lambda b: hashlib.sha256(b).hexdigest()
# Lossless 20x20 synthetic PNG; generated using standard library only.
def _chunk(kind, data):
    return (struct.pack(">I", len(data)) + kind + data
            + struct.pack(">I", zlib.crc32(kind + data)))
PNG = (b"\x89PNG\r\n\x1a\n"
       + _chunk(b"IHDR", struct.pack(">IIBBBBB", 20, 20, 8, 2, 0, 0, 0))
       + _chunk(b"IDAT", zlib.compress((b"\x00" + b"\xef" * 60) * 20))
       + _chunk(b"IEND", b""))


class PrivateReviewAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.video = self.root / "video.mp4"
        self.video.write_bytes(b"synthetic never a real clip")
        self.sha = SHA(self.video.read_bytes())
        self.manifest = self.root / "manifest.json"
        self.manifest.write_text(json.dumps({
            "schema_version": "source_river_geometry_v0_1",
            "source_session": "synthetic_review", "source_sha256": self.sha,
            "frame_size": [100, 100], "reviewed_frame_span": [0, 5],
            "development_only": True, "excluded_from_formal_promotion": True,
            "zones": [
                {"actor": "opponent", "bbox": [.01, .01, .4, .4], "single_width": [.15, .25], "single_height": [.15, .25]},
                {"actor": "player", "bbox": [.50, .50, .4, .4], "single_width": [.15, .25], "single_height": [.15, .25]},
            ],
        }), encoding="utf-8")
        self.queue = self.root / "review_queue.json"
        self.candidates = []
        for rid, frame, actor in (("c1", 1, "opponent"), ("c2", 2, "opponent"), ("c3", 3, "opponent")):
            (self.root / f"{rid}.png").write_bytes(PNG)
            self.candidates.append({
                "review_id": rid, "frame": frame, "screen_side_actor": actor,
                "crop_file": f"{rid}.png", "crop_sha256": SHA(PNG),
                "normalized_bbox": [.10, .10, .2, .2], "geometry_kind": "single_face",
                "tile_id": None, "turn_actor": None, "action_kind": None,
                "review_status": "pending",
            })
        self.queue_data = {
            "schema_version": "source_river_review_queue_v0_1",
            "source_session": "synthetic_review", "source_sha256": self.sha,
            "frame_range": [0, 5], "review_kind": "private_unlabeled_development_geometry",
            "formal_promotion_evidence": False, "safe_for_executor": False,
            "label_reuse_forbidden": True, "candidates": self.candidates,
        }
        self.review = {
            "schema_version": "source_river_review_decisions_v0_1", "source_session": "synthetic_review",
            "source_sha256": self.sha, "review_kind": "development_visual_review",
            "excluded_from_formal_promotion": True, "decisions": [],
        }
        self._write()

    def _write(self):
        self.queue.write_text(json.dumps(self.queue_data), encoding="utf-8")
        self.review["queue_sha256"] = SHA(self.queue.read_bytes())
        (self.root / "decisions.json").write_text(json.dumps(self.review), encoding="utf-8")

    def audit(self, verify=False):
        return audit_review(queue_path=self.queue, decisions_path=self.root / "decisions.json",
                            source_video=self.video, manifest_path=self.manifest, verify_pixels=verify)

    def test_unreviewed_and_proposed_not_approved(self):
        self.review["decisions"] = [{"review_id": "c1", "status": "proposed", "tile_id": "R",
                                     "same_physical_tile_as": None, "evidence_frames": [1], "reviewer": None}]
        self._write()
        report = self.audit()
        self.assertEqual(report["statuses"], {"approved": 0, "pending": 2, "proposed": 1, "rejected": 0})
        self.assertEqual(report["approved_unique_tiles"], 0)
        self.assertEqual(report["action_predictions"], 0)
        self.assertFalse(report["runtime_identity_ready"])
        self.assertNotIn("source_sha256", report)

    def test_explicit_approval_and_verified_same_tile_repeat(self):
        self.review["decisions"] = [
            {"review_id": "c1", "status": "approved", "tile_id": "R", "evidence_frames": [1], "reviewer": "manual_review"},
            {"review_id": "c2", "status": "approved", "tile_id": "R", "same_physical_tile_as": "c1",
             "evidence_frames": [1, 2], "reviewer": "manual_review"},
        ]
        self._write()
        with patch("workspace.vision.source_river_review_audit.verify_source_crops"):
            report = self.audit(verify=True)
        self.assertEqual((report["approved_unique_tiles"], report["approved_repeat_tracks"]), (1, 1))
        self.assertEqual(report["statuses"]["pending"], 1)

    def test_source_hash_crop_hash_and_queue_digest_reject_tamper(self):
        self.review["queue_sha256"] = "0" * 64
        (self.root / "decisions.json").write_text(json.dumps(self.review))
        with self.assertRaisesRegex(ValueError, "decision provenance"):
            self.audit()
        self._write()
        self.video.write_bytes(b"different video")
        with self.assertRaisesRegex(ValueError, "source video SHA256"):
            self.audit()
        self.video.write_bytes(b"synthetic never a real clip")
        (self.root / "c1.png").write_bytes(b"mutated")
        with self.assertRaisesRegex(ValueError, "crop SHA256"):
            self.audit()

    def test_manual_approval_requires_source_frame_and_reviewer(self):
        self.review["decisions"] = [{"review_id": "c1", "status": "approved", "tile_id": "R",
                                     "evidence_frames": [], "reviewer": ""}]
        self._write()
        with self.assertRaisesRegex(ValueError, "explicit reviewer"):
            self.audit()
        self.review["decisions"][0]["reviewer"] = "manual_review"
        self._write()
        with self.assertRaisesRegex(ValueError, "source frame evidence"):
            self.audit()

    def test_repeat_requires_earlier_same_actor_matching_approved_anchor(self):
        self.review["decisions"] = [{"review_id": "c2", "status": "approved", "tile_id": "B",
                                     "same_physical_tile_as": "c1", "evidence_frames": [1, 2], "reviewer": "manual_review"}]
        self._write()
        with self.assertRaisesRegex(ValueError, "matching approved unique anchor"):
            self.audit()
        self.review["decisions"].append({"review_id": "c1", "status": "approved", "tile_id": "R",
                                         "evidence_frames": [1], "reviewer": "manual_review"})
        self._write()
        with self.assertRaisesRegex(ValueError, "matching approved unique anchor"):
            self.audit()
        self.review["decisions"][0]["same_physical_tile_as"] = "c3"
        self._write()
        with self.assertRaisesRegex(ValueError, "prior same-actor"):
            self.audit()

    def test_repeat_without_two_frames_cannot_be_approved(self):
        self.review["decisions"] = [
            {"review_id": "c1", "status": "approved", "tile_id": "R",
             "evidence_frames": [1], "reviewer": "manual_review"},
            {"review_id": "c2", "status": "approved", "tile_id": "R",
             "same_physical_tile_as": "c1", "evidence_frames": [2],
             "reviewer": "manual_review"},
        ]
        self._write()
        with self.assertRaisesRegex(ValueError, "both source frames"):
            self.audit()

    def test_disabling_pixel_check_never_reports_approved_evidence(self):
        self.review["decisions"] = [{
            "review_id": "c1", "status": "approved", "tile_id": "R",
            "evidence_frames": [1], "reviewer": "manual_review",
        }]
        self._write()
        report = self.audit(verify=False)
        self.assertFalse(report["source_pixels_verified"])
        self.assertEqual(report["approved_unique_tiles"], 0)
        self.assertEqual(report["signed_off_but_source_pixels_unverified"], 1)

    def test_unreviewed_zone_does_not_create_a_label(self):
        self.queue_data["candidates"][0]["normalized_bbox"] = [.51, .51, .2, .2]
        self._write()
        with self.assertRaisesRegex(ValueError, "outside source-reviewed river zone"):
            self.audit()

    def test_no_event_truth_turn_or_action_fields_and_no_queue_labels(self):
        self.review["decisions"] = [{"review_id": "c1", "status": "proposed", "tile_id": "R",
                                     "action_kind": "DISCARD"}]
        self._write()
        with self.assertRaisesRegex(ValueError, "invalid fields"):
            self.audit()
        self.review["decisions"] = []
        self.queue_data["candidates"][0]["tile_id"] = "R"
        self._write()
        with self.assertRaisesRegex(ValueError, "unlabeled"):
            self.audit()

    def test_review_span_and_crop_traversal_fail_closed(self):
        self.queue_data["frame_range"] = [0, 6]
        self._write()
        with self.assertRaisesRegex(ValueError, "reviewed source interval"):
            self.audit()
        self.queue_data["frame_range"] = [0, 5]
        self.queue_data["candidates"][0]["crop_file"] = "../foreign.png"
        self._write()
        with self.assertRaisesRegex(ValueError, "crop name"):
            self.audit()


if __name__ == "__main__":
    unittest.main()
