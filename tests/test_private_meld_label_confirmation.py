"""Issue #69: synthetic tests for explicit PRIVATE G01-G12 face confirmation.

Do not ship the user's 36 real crops, proposals, room metadata, private SHA
values or exact source clip filenames into the public repository.
"""
from __future__ import annotations

import hashlib
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from workspace.vision.private_meld_label_confirmation import (
    confirm_existing_private_faces,
)


class PrivateMeldLabelConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / "pending.zip"
        self.confirmation = self.root / "declaration.json"
        self.registry = self.root / "private_registry.json"
        self.sheet = b"synthetic screenshot of exact review sheet"
        self.pngs = {
            f"sample_face_{i}.png": b"synthetic lossless private PNG" + bytes([i])
            for i in range(1, 4)
        }
        sha = "a" * 64
        self.registry_data = {
            "schema_version": "private_meld_sources_v0_1",
            "sources": [{
                "clip": "sample.mp4", "sha256": sha,
                "match_group": "one_real_match_only"
            }],
        }
        self.manifest = {
            "schema_version": "private_existing_evidence_review_v0_1",
            "development_only": True,
            "requires_human_review": True,
            "source_disjoint_holdout": False,
            "identity_accuracy": None,
            "extracted_group_count": 1,
            "extracted_face_slots": 3,
            "groups": [{
                "clip": "sample.mp4", "source_video_sha256": sha,
                "match_group": "one_real_match_only",
                "time_seconds": 1.0,
                "frame_index_approx": 30,
                "frame_resolution": [1046, 480],
                "group_pixel_bbox": [100, 400, 120, 70],
                "human_approved": False,
                "formal_promotion_evidence": False,
                "tile_identity_policy": "UNKNOWN",
                "faces": [{
                    "index": i,
                    "relative_crop_file": f"sample_face_{i+1}.png",
                    "pixel_bbox": [100+i*40, 400, 40, 70],
                    "tile_id": "UNKNOWN",
                    "review_status": "pending_human_adjudication",
                } for i in range(3)],
            }],
        }
        self.proposals = {
            "user_confirmed_labels": 0,
            "pixel_verified_faces": 3,
            "pixel_verified_groups": 1,
            "groups_review": [{
                "group_no": 1,
                "clip": "sample.mp4",
                "match_group": "one_real_match_only",
                "all_three_crops_match_source_pixels": True,
                "faces": [{
                    "face_index": i,
                    "crop_file": f"sample_face_{i+1}.png",
                    "crop_sha256": hashlib.sha256(
                        self.pngs[f"sample_face_{i+1}.png"]
                    ).hexdigest(),
                    "visual_candidate": f"P{i+4}",
                } for i in range(3)],
            }],
        }
        self.out = self.root / "confirmed.json"
        self.write_private_fixture()

    def write_private_fixture(self, *, extra=None):
        self.registry.write_text(json.dumps(self.registry_data), "utf-8")
        with ZipFile(self.archive, "w") as z:
            z.writestr("pending_faces/manifest.json", json.dumps(self.manifest))
            z.writestr(
                "private_pixel_integrity_and_pending_proposals.json",
                json.dumps(self.proposals)
            )
            z.writestr("private_source_registry_for_local_reaudit.json",
                       json.dumps(self.registry_data))
            z.writestr("private_review_visual_proposals.jpg", self.sheet)
            for name, content in self.pngs.items():
                z.writestr("pending_faces/" + name, content)
            for name, content in (extra or {}).items():
                z.writestr(name, content)
        self.confirmation.write_text(json.dumps({
            "schema_version": "private_meld_review_user_confirmation_v0_1",
            "source_packet_sha256": hashlib.sha256(
                self.archive.read_bytes()
            ).hexdigest(),
            "review_sheet_sha256": hashlib.sha256(
                self.sheet
            ).hexdigest(),
            "confirmed_group_ids": ["G01"],
            "user_explicitly_confirmed_all": True,
        }), "utf-8")

    def approve(self, *, audited=None):
        report = audited if audited is not None else {
            "source_verified_groups": 1,
            "source_verified_faces": 3,
            "original_matches": 1,
            "formal_promotion_evidence": False,
        }
        with patch(
            "workspace.vision.private_meld_label_confirmation."
            "audit_private_meld_packet",
            return_value=report,
        ) as pixel_audit:
            out = confirm_existing_private_faces(
                archive_path=self.archive,
                user_declaration_path=self.confirmation,
                videos_dir=self.root,
                private_registry_path=self.registry,
                output_path=self.out,
                expected_groups=1, expected_faces=3,
            )
            if pixel_audit.called:
                flat_zip = pixel_audit.call_args.args[0]
                # The temporary normalized ZIP must contain exactly the
                # original pending 3 faces and no prior approval metadata.
                # Test within the mock side-effect if byte inspection is
                # added later; here count and no-promotion are asserted.
            return out

    def test_explicit_sheet_bound_approval_keeps_runtime_unknown(self):
        out = self.approve()
        self.assertEqual(out["human_confirmed_faces"], 3)
        self.assertEqual(out["original_match_groups"], 1)
        saved = json.loads(self.out.read_text("utf-8"))
        self.assertEqual(
            [x["approved_tile_id"] for x in saved["labels"]],
            ["P4", "P5", "P6"],
        )
        self.assertTrue(all(
            x["public_action_kind"] == "UNKNOWN"
            and x["safe_for_runtime"] is False
            and x["formal_promotion_evidence"] is False
            for x in saved["labels"]
        ))
        self.assertFalse(saved["independent_blind_holdout"])
        self.assertFalse(out["safe_for_runtime"])

    def test_archive_tamper_refused_before_pixel_audit(self):
        self.archive.write_bytes(self.archive.read_bytes() + b"unexpected bytes")
        with self.assertRaisesRegex(ValueError, "packet SHA mismatch"):
            self.approve()
        self.assertFalse(self.out.exists())

    def test_wrong_review_sheet_or_missing_explicit_confirmation_refused(self):
        data = json.loads(self.confirmation.read_text("utf-8"))
        data["review_sheet_sha256"] = "0" * 64
        self.confirmation.write_text(json.dumps(data), "utf-8")
        with self.assertRaisesRegex(ValueError, "review sheet SHA"):
            self.approve()
        data["review_sheet_sha256"] = hashlib.sha256(self.sheet).hexdigest()
        data["user_explicitly_confirmed_all"] = False
        self.confirmation.write_text(json.dumps(data), "utf-8")
        with self.assertRaisesRegex(ValueError, "explicit scoped"):
            self.approve()

    def test_proposed_identity_must_match_original_crop_and_known_class(self):
        self.proposals["groups_review"][0]["faces"][1]["visual_candidate"] = "BAD"
        self.write_private_fixture()
        with self.assertRaisesRegex(ValueError, "invalid proposed"):
            self.approve()
        self.proposals["groups_review"][0]["faces"][1][
            "visual_candidate"
        ] = "P5"
        self.proposals["groups_review"][0]["faces"][1]["crop_sha256"] = "0"*64
        self.write_private_fixture()
        with self.assertRaisesRegex(ValueError, "altered or duplicate"):
            self.approve()

    def test_invalid_or_out_of_order_face_cannot_inherit_blanket_approval(self):
        self.proposals["groups_review"][0]["faces"][1]["face_index"] = 0
        self.write_private_fixture()
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.approve()
        self.proposals["groups_review"][0]["faces"][1]["face_index"] = 1
        self.manifest["groups"][0]["faces"][1]["review_status"] = "approved"
        self.write_private_fixture()
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.approve()

    def test_source_registry_conflict_and_path_traversal_refused(self):
        self.registry_data["sources"][0]["sha256"] = "b"*64
        # Re-seal manifest archive, then mutate the independent registry.
        self.write_private_fixture()
        payload = json.loads(self.registry.read_text("utf-8"))
        payload["sources"][0]["match_group"] = "fake_other_match"
        self.registry.write_text(json.dumps(payload), "utf-8")
        with self.assertRaisesRegex(ValueError, "source registry differs"):
            self.approve()
        self.registry.write_text(json.dumps(self.registry_data), "utf-8")
        self.write_private_fixture(extra={"../../private/leak.png": b"secret"})
        with self.assertRaisesRegex(ValueError, "unsafe"):
            self.approve()

    def test_pixel_verification_failure_cannot_emit_approved_labels(self):
        with self.assertRaisesRegex(ValueError, "pixel audit did not pass"):
            self.approve(audited={
                "source_verified_groups": 1,
                "source_verified_faces": 2,
                "original_matches": 1,
                "formal_promotion_evidence": False,
            })
        self.assertFalse(self.out.exists())

    def test_never_write_private_label_file_inside_public_repo(self):
        from workspace.vision import private_meld_label_confirmation as m
        with patch.object(Path, "resolve", autospec=True) as resolve:
            # Use an actual checkout path, which must be rejected *before*
            # opening private video or committing any private pixels.
            resolve.side_effect = lambda instance: instance
            with self.assertRaisesRegex(ValueError, "inside checkout"):
                confirm_existing_private_faces(
                    archive_path=self.archive,
                    user_declaration_path=self.confirmation,
                    videos_dir=self.root,
                    private_registry_path=self.registry,
                    output_path=Path(m.__file__).resolve().parents[2] /
                                "unsafe_confirmed.json",
                    expected_groups=1, expected_faces=3,
                )


if __name__ == "__main__":
    unittest.main()
