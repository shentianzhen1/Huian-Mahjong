import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from workspace.vision.tiles_runtime_v0_2.restore_private_candidate import restore_candidate


class RestorePrivateCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / "runtime"
        self.base.mkdir()
        (self.base / "labels.jsonl").write_text("", encoding="utf-8")
        self.output = self.root / "candidate"
        self.package = self.root / "private.zip"
        self.pixels = b"synthetic-test-bytes-not-private-pixels"
        self.row = dict(image="templates/hand/dev.png", tile_id="M8", region="hand_region",
                        approved=True, status="approved", source_session="test_session",
                        original_match_group="test_match", sha256="a" * 64,
                        asset_sha256=hashlib.sha256(self.pixels).hexdigest())

    def pack(self, row=None, pixels=None):
        row = self.row if row is None else row
        with zipfile.ZipFile(self.package, "w") as z:
            z.writestr("support19m8_metadata.json", json.dumps([row]))
            z.writestr(row["image"], self.pixels if pixels is None else pixels)

    def test_restores_and_does_not_modify_runtime(self):
        self.pack()
        result = restore_candidate(self.package, self.base, self.output)
        self.assertEqual(result["support_count"], 1)
        self.assertEqual(result["candidate_label_count"], 1)
        self.assertFalse(result["safe_for_runtime"])
        self.assertEqual((self.base / "labels.jsonl").read_bytes(), b"")
        self.assertFalse((self.base / self.row["image"]).exists())

    def test_bad_hash_creates_no_output(self):
        self.pack(pixels=b"modified")
        with self.assertRaisesRegex(ValueError, "SHA256"):
            restore_candidate(self.package, self.base, self.output)
        self.assertFalse(self.output.exists())

    def test_legacy_rows_restore_without_inventing_match_lineage(self):
        row = dict(self.row)
        row.pop("original_match_group")
        self.pack(row)
        result = restore_candidate(self.package, self.base, self.output)
        self.assertEqual(result["support_rows_without_embedded_match_group"], 1)
        restored = json.loads((self.output / "labels.jsonl").read_text())
        self.assertNotIn("original_match_group", restored)
        self.assertFalse(result["source_session_is_independence_evidence"])

    def test_traversal_rejected(self):
        self.pack(dict(self.row, image="templates/hand/../../escape.png"))
        with self.assertRaisesRegex(ValueError, "path"):
            restore_candidate(self.package, self.base, self.output)

    def test_existing_output_is_preserved(self):
        self.output.mkdir()
        sentinel = self.output / "user.txt"
        sentinel.write_text("keep")
        self.pack()
        with self.assertRaisesRegex(ValueError, "exist"):
            restore_candidate(self.package, self.base, self.output)
        self.assertEqual(sentinel.read_text(), "keep")

    def test_nested_runtime_output_rejected(self):
        self.pack()
        with self.assertRaisesRegex(ValueError, "separate"):
            restore_candidate(self.package, self.base, self.base / "candidate")

    def test_unapproved_and_gold_templates_rejected(self):
        for change in [dict(approved=1), dict(status="review"), dict(gold_skin_only=True)]:
            with self.subTest(change=change):
                self.pack(dict(self.row, **change))
                with self.assertRaisesRegex(ValueError, "metadata"):
                    restore_candidate(self.package, self.base, self.output)

    def test_duplicate_private_path_rejected(self):
        with zipfile.ZipFile(self.package, "w") as z:
            z.writestr("support19m8_metadata.json", json.dumps([self.row, self.row]))
            z.writestr(self.row["image"], self.pixels)
        with self.assertRaisesRegex(ValueError, "collision"):
            restore_candidate(self.package, self.base, self.output)
