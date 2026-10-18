import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from .legacy_reviewed_batch import scan_legacy_support_gaps


class LegacyReviewedBatchTests(unittest.TestCase):
    def runtime(self, root):
        runtime = root / "runtime"
        runtime.mkdir()
        rows = [
            dict(tile_id="M1", region="hand_region", approved=True,
                 source_session="same_match"),
            dict(tile_id="M1", region="draw_region", approved=True,
                 source_session="same_match"),
            dict(tile_id="M1", region="draw_visual", approved=True,
                 source_session="other_match"),
            dict(tile_id="M2", region="hand_region", approved=True,
                 source_session="same_match"),
            dict(tile_id="M2", region="gold_region", approved=True,
                 source_session="other_match"),
            dict(tile_id="M2", region="hand_region", approved=True,
                 source_session="gold_skin", gold_skin_only=True),
            dict(tile_id="M2", region="hand_region", approved=False,
                 source_session="unreviewed"),
        ]
        (runtime / "labels.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8",
        )
        return runtime

    def test_current_gaps_use_pooled_concealed_approved_ordinary_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = self.runtime(root)
            before = (runtime / "labels.jsonl").read_bytes()
            result = scan_legacy_support_gaps(root / "missing", runtime)
            self.assertNotIn("M1", result["target_classes"])
            m2 = next(item for item in result["items"] if item["tile_id"] == "M2")
            self.assertEqual(m2["current_stored_session_count"], 1)
            self.assertEqual(m2["status"], "LEGACY_LABELS_UNAVAILABLE")
            self.assertIsNone(m2["candidate_count"])
            self.assertIsNone(result["legacy_approved_label_count"])
            self.assertFalse(result["stored_sessions_prove_original_match_independence"])
            self.assertEqual((runtime / "labels.jsonl").read_bytes(), before)
            self.assertFalse((runtime / "templates").exists())

    def test_batch_separates_gold_candidates_and_preserves_runtime_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = self.runtime(root)
            legacy = root / "legacy"
            (legacy / "labels").mkdir(parents=True)
            Image.new("RGB", (44, 68), "white").save(legacy / "tile.png")
            rows = [dict(image="tile.png", bbox=[0, 0, 44, 68], tile_id=tile,
                         region=region, status=status)
                    for tile, region, status in (
                        ("M2", "draw_region", "approved"),
                        ("M4", "gold_region", "approved"),
                        ("M7", "hand_region", "rejected"),
                    )]
            (legacy / "labels" / "tiles.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8",
            )
            before = (runtime / "labels.jsonl").read_bytes()
            result = scan_legacy_support_gaps(legacy, runtime, tile_ids=["M2", "M4", "M7"])
            by_tile = {item["tile_id"]: item for item in result["items"]}
            self.assertEqual(by_tile["M2"]["concealed_candidate_count"], 1)
            self.assertEqual(by_tile["M4"]["candidate_count"], 1)
            self.assertEqual(by_tile["M4"]["concealed_candidate_count"], 0)
            self.assertEqual(by_tile["M7"]["candidate_count"], 0)
            self.assertFalse(result["safe_for_hint"])
            self.assertEqual((runtime / "labels.jsonl").read_bytes(), before)
            self.assertFalse((runtime / "templates").exists())
            self.assertTrue((runtime / "work/legacy_reviewed_recovery/M2/contact_sheet.jpg").is_file())

    def test_missing_runtime_inventory_and_invalid_classes_do_not_write_plans(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(FileNotFoundError):
                scan_legacy_support_gaps(root / "legacy", root / "absent")
            runtime = self.runtime(root)
            with self.assertRaises(ValueError):
                scan_legacy_support_gaps(root / "legacy", runtime, tile_ids=["../M2"])
            self.assertFalse((runtime / "work").exists())


if __name__ == "__main__":
    unittest.main()
