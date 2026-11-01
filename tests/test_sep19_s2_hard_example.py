import hashlib
from pathlib import Path
import unittest

from workspace.vision.tiles_v0_1.labels import approved_labels


SOURCE_SHA = "1560c1e04a632f07dc5f53947ba3080ed93ff927a7bd028a457f3415b0bc69a3"
TILE_ID = "tile_918e71bb57c31ab7"
ASSET_SHA = "918e71bb57c31ab733fa0f21fbf375675d7d3df84bed671f48a17204e63b02bf"


class Sep19S2HardExampleTests(unittest.TestCase):
    def test_reviewed_hard_example_is_same_match_augmentation_not_independent_source(self):
        root = Path(__file__).resolve().parents[1] / "dataset" / "tiles_runtime_v0_2"
        row = next(item for item in approved_labels(root) if item.get("id") == TILE_ID)

        self.assertEqual(row["tile_id"], "S2")
        self.assertEqual(row["sha256"], SOURCE_SHA)
        self.assertEqual(row["source_session"], "session_eight_hand_match_a")
        self.assertEqual(row["source_frame"], 1508)
        self.assertEqual(row["bbox"], [300, 407, 46, 71])
        self.assertEqual(
            row["selection_policy"],
            "sep19_only_lowest_confidence_clear_normal_height_s2_candidate",
        )
        self.assertFalse(row["selection_used_sep26_holdout"])
        self.assertFalse(row["counts_as_independent_original_match"])

        asset = root / row["image"]
        self.assertTrue(asset.is_file())
        self.assertEqual(hashlib.sha256(asset.read_bytes()).hexdigest(), ASSET_SHA)


if __name__ == "__main__":
    unittest.main()
