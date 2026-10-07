import tempfile
from pathlib import Path
import unittest

from workspace.vision.concealed_template_match_lineage import ConcealedTemplateSource
from workspace.vision.tiles_runtime_v0_2.concealed_mobilenet_ab import (
    FROZEN_CONFIDENCE_THRESHOLD,
    resolve_private_crop,
    select_training_labels,
)


class ConcealedMobileNetABTests(unittest.TestCase):
    def test_threshold_stays_frozen_and_session_name_is_not_independence(self):
        self.assertEqual(FROZEN_CONFIDENCE_THRESHOLD, 0.82)
        same_sha = "a" * 64
        other_sha = "b" * 64
        unknown_sha = "c" * 64
        lineage = {
            same_sha: ConcealedTemplateSource(same_sha, "query-match", "evidence/a.json"),
            other_sha: ConcealedTemplateSource(other_sha, "other-match", "evidence/b.json"),
        }
        labels = [
            {
                "tile_id": "M2",
                "region": "hand_region",
                "approved": True,
                "sha256": same_sha,
                "source_session": "looks-different-but-same-match",
            },
            {
                "tile_id": "M2",
                "region": "draw_visual",
                "approved": True,
                "sha256": other_sha,
                "source_session": "same-session-name-does-not-matter",
            },
            {
                "tile_id": "P2",
                "region": "draw_visual",
                "approved": True,
                "sha256": unknown_sha,
                "source_session": "unique-looking-session",
            },
        ]

        selected, report = select_training_labels(
            labels,
            lineage,
            query_match_groups={"query-match"},
            strict_original_match_lineage=True,
        )

        self.assertEqual([row["tile_id"] for row in selected], ["M2"])
        self.assertEqual(report["excluded_same_original_match_count"], 1)
        self.assertEqual(report["excluded_missing_lineage_count"], 1)
        self.assertFalse(report["source_session_used_as_independence_signal"])

    def test_permissive_mode_is_explicitly_development_only(self):
        unknown_sha = "d" * 64
        selected, report = select_training_labels(
            [
                {
                    "tile_id": "P2",
                    "region": "draw_visual",
                    "approved": True,
                    "sha256": unknown_sha,
                }
            ],
            {},
            query_match_groups={"query-match"},
            strict_original_match_lineage=False,
        )
        self.assertEqual(len(selected), 1)
        self.assertFalse(selected[0]["_lineage_qualified"])
        self.assertEqual(report["development_included_unresolved_lineage_count"], 1)
        self.assertFalse(report["formal_promotion_evidence"])

    def test_private_crop_ref_cannot_escape_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample = root / "sample-a"
            sample.mkdir()
            crop = sample / "tile.png"
            crop.write_bytes(b"not-decoded-in-this-test")
            self.assertEqual(
                resolve_private_crop(root, "private://sample-a/tile.png"),
                crop.resolve(),
            )
            with self.assertRaisesRegex(ValueError, "escapes crop root"):
                resolve_private_crop(root, "private://../outside.png")


if __name__ == "__main__":
    unittest.main()
