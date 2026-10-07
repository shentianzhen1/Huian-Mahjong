import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from workspace.vision.tiles_v0_1.labels import approved_labels


SOURCE_SHA = "1560c1e04a632f07dc5f53947ba3080ed93ff927a7bd028a457f3415b0bc69a3"
ASSET_SHA = "34928d2442cfb53bf9687fd86eaecdac74ee7fd16faac2075e9c45bf32e4bd13"
TILE_ID = "tile_34928d2442cfb53b"


class ReviewedLabelAdditionTests(unittest.TestCase):
    def test_reviewed_additions_are_merged_after_primary_labels(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            primary = [
                {"id": "base-approved", "tile_id": "S1", "status": "approved"},
                {"id": "base-review", "tile_id": "S9", "status": "review"},
            ]
            root.joinpath("labels.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in primary),
                encoding="utf-8",
            )
            additions = root / "labels_reviewed_additions"
            additions.mkdir()
            additions.joinpath("2026-10-07.jsonl").write_text(
                json.dumps({"id": "addition-approved", "tile_id": "S2", "approved": True}) + "\n",
                encoding="utf-8",
            )

            rows = approved_labels(root)

            self.assertEqual([row["id"] for row in rows], ["base-approved", "addition-approved"])

    def test_committed_sep19_s2_reviewed_addition_has_exact_lineage_and_asset_hash(self):
        root = Path(__file__).resolve().parents[1] / "dataset" / "tiles_runtime_v0_2"
        rows = approved_labels(root)
        row = next(item for item in rows if item.get("id") == TILE_ID)

        self.assertEqual(row["tile_id"], "S2")
        self.assertEqual(row["sha256"], SOURCE_SHA)
        self.assertEqual(row["source_frame"], 795)
        self.assertEqual(row["bbox"], [347, 407, 46, 71])
        self.assertEqual(row["source_session"], "session_eight_hand_match_a")
        self.assertEqual(row["asset_sha256"], ASSET_SHA)
        self.assertEqual(row["crop_policy"], "reviewed_exact_bbox_v0_1")
        self.assertFalse(row["gold_skin_only"])

        asset = root / row["image"]
        self.assertTrue(asset.is_file())
        self.assertEqual(hashlib.sha256(asset.read_bytes()).hexdigest(), ASSET_SHA)


if __name__ == "__main__":
    unittest.main()
