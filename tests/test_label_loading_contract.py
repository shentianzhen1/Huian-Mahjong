"""Synthetic compatibility contracts for primary and reviewed JSONL labels."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from workspace.vision.tiles_v0_1.labels import approved_labels


class LabelLoadingContractTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def write(self, name, rows):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return path

    def ids(self):
        return [row["id"] for row in approved_labels(self.root)]

    def test_missing_dataset_is_empty(self):
        self.assertEqual(approved_labels(self.root / "missing"), [])

    def test_legacy_primary_remains_supported(self):
        self.write("labels/tiles.jsonl", [{"id": "legacy", "status": "approved"}])
        self.assertEqual(self.ids(), ["legacy"])

    def test_runtime_primary_takes_precedence_over_legacy(self):
        self.write("labels/tiles.jsonl", [{"id": "legacy", "approved": True}])
        self.write("labels.jsonl", [{"id": "runtime", "approved": True}])
        self.assertEqual(self.ids(), ["runtime"])

    def test_additions_have_stable_filename_order_after_primary(self):
        self.write("labels.jsonl", [{"id": "base", "status": "approved"}])
        self.write("labels_reviewed_additions/z.jsonl", [{"id": "last", "approved": True}])
        self.write("labels_reviewed_additions/a.jsonl", [{"id": "first", "approved": True}])
        self.write("labels_reviewed_additions/ignored.txt", [{"id": "ignored", "approved": True}])
        self.assertEqual(self.ids(), ["base", "first", "last"])

    def test_only_approved_rows_are_loaded_from_each_file(self):
        rows = [
            {"id": "status", "status": "approved"},
            {"id": "boolean", "approved": True},
            {"id": "review", "status": "review"},
            {"id": "rejected", "status": "rejected"},
        ]
        self.write("labels.jsonl", rows)
        self.write("labels_reviewed_additions/a.jsonl", rows)
        self.assertEqual(self.ids(), ["status", "boolean", "status", "boolean"])

    def test_additions_work_without_primary(self):
        self.write("labels_reviewed_additions/a.jsonl", [{"id": "only", "approved": True}])
        self.assertEqual(self.ids(), ["only"])

    def test_malformed_addition_is_reported_instead_of_silently_skipped(self):
        self.write("labels.jsonl", [{"id": "base", "approved": True}])
        path = self.write("labels_reviewed_additions/a.jsonl", [])
        path.write_text("{invalid json\n", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            approved_labels(self.root)


if __name__ == "__main__":
    unittest.main()
