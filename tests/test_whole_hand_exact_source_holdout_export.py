import unittest

from workspace.vision.tiles_runtime_v0_2.whole_hand_exact_source_holdout_export import (
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


if __name__ == "__main__":
    unittest.main()
