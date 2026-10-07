import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from workspace.vision.tiles_runtime_v0_2.whole_hand_exact_source_holdout_export import (
    _build_filtered_dataset_view,
    _filter_label_rows,
    _normalize_shas,
)


SHA_A = "a" * 64
SHA_B = "b" * 64


class WholeHandExactSourceHoldoutExportTests(unittest.TestCase):
    def test_exact_source_filter_removes_only_matching_sha(self):
        rows = [
            {"tile_id": "M6", "sha256": SHA_A, "gold_skin_only": True},
            {"tile_id": "P3", "sha256": SHA_A, "gold_skin_only": False},
            {"tile_id": "P3", "sha256": SHA_B, "gold_skin_only": False},
            {"tile_id": "P4", "sha256": None, "gold_skin_only": False},
        ]

        kept, stats = _filter_label_rows(rows, [SHA_A])

        self.assertEqual([row["sha256"] for row in kept], [SHA_B, None])
        self.assertEqual(stats["input_label_count"], 4)
        self.assertEqual(stats["kept_label_count"], 2)
        self.assertEqual(stats["excluded_label_count"], 2)
        self.assertEqual(stats["excluded_gold_skin_label_count"], 1)
        self.assertEqual(stats["excluded_tile_ids"], ["M6", "P3"])
        self.assertEqual(stats["filter_key"], "exact_source_sha256")

    def test_multiple_exclusions_are_deduplicated_and_normalized(self):
        self.assertEqual(_normalize_shas([SHA_B.upper(), SHA_A, SHA_B]), (SHA_A, SHA_B))

    def test_invalid_sha_fails_closed(self):
        with self.assertRaises(ValueError):
            _normalize_shas(["not-a-sha"])

    def test_filtered_scratch_view_never_mutates_source_labels(self):
        with TemporaryDirectory() as source_tmp, TemporaryDirectory() as scratch_tmp:
            source_root = Path(source_tmp)
            (source_root / "templates" / "hand").mkdir(parents=True)
            (source_root / "templates" / "hand" / "dummy.png").write_bytes(b"immutable-template")
            source_rows = [
                {"tile_id": "M6", "sha256": SHA_A, "approved": True},
                {"tile_id": "P3", "sha256": SHA_B, "approved": True},
            ]
            source_labels = source_root / "labels.jsonl"
            original_bytes = "".join(
                json.dumps(row, ensure_ascii=False) + "\n" for row in source_rows
            ).encode("utf-8")
            source_labels.write_bytes(original_bytes)

            filtered_root, stats = _build_filtered_dataset_view(
                source_root,
                Path(scratch_tmp),
                [SHA_A],
            )

            self.assertEqual(source_labels.read_bytes(), original_bytes)
            self.assertEqual(stats["excluded_label_count"], 1)
            filtered_rows = [
                json.loads(line)
                for line in (filtered_root / "labels.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(filtered_rows, [source_rows[1]])
            self.assertEqual(
                (source_root / "templates" / "hand" / "dummy.png").read_bytes(),
                b"immutable-template",
            )


if __name__ == "__main__":
    unittest.main()
