import tempfile
from pathlib import Path
import unittest

try:
    import numpy as np
    from PIL import Image
except ImportError:  # Core-only environments may omit Vision dependencies.
    np = None
    Image = None

from workspace.vision.concealed_template_match_lineage import ConcealedTemplateSource
from workspace.vision.tiles_runtime_v0_2.concealed_mobilenet_ab import (
    APPEARANCE_AUGMENTATION_VERSION,
    FROZEN_CONFIDENCE_THRESHOLD,
    OBSERVED_SHADOW_DARKEN_DELTA,
    OBSERVED_SHADOW_FULL_BAND_START,
    _appearance_variants,
    _bottom_shadow_variant,
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

    @unittest.skipUnless(Image is not None and np is not None, "Vision deps unavailable")
    def test_observed_bottom_shadow_variant_is_deterministic_and_geometry_safe(self):
        source = Image.new("RGB", (40, 100), (200, 200, 200))

        first = _bottom_shadow_variant(source)
        second = _bottom_shadow_variant(source)
        first_array = np.asarray(first)
        second_array = np.asarray(second)

        self.assertEqual(first.size, source.size)
        self.assertTrue(np.array_equal(first_array, second_array))
        self.assertEqual(float(first_array[50].mean()), 200.0)
        full_band_row = int(round(source.height * OBSERVED_SHADOW_FULL_BAND_START))
        expected_bottom = 200.0 - OBSERVED_SHADOW_DARKEN_DELTA
        self.assertAlmostEqual(float(first_array[full_band_row].mean()), expected_bottom)
        self.assertAlmostEqual(float(first_array[-1].mean()), expected_bottom)

    @unittest.skipUnless(Image is not None and np is not None, "Vision deps unavailable")
    def test_appearance_bank_includes_one_observed_shadow_variant(self):
        source = Image.new("RGB", (40, 100), (200, 200, 200))
        variants = _appearance_variants(source)

        self.assertEqual(APPEARANCE_AUGMENTATION_VERSION, "v0_2_real_bottom_shadow")
        self.assertEqual(len(variants), 9)
        self.assertTrue(all(image.size == (224, 224) for image in variants))
        # Index 7 is the new shadow variant; its lower tile band must be darker
        # than the ordinary base while the input geometry is still unchanged.
        base = np.asarray(variants[0]).astype(np.float32)
        shadow = np.asarray(variants[7]).astype(np.float32)
        self.assertLess(float(shadow[180:205].mean()), float(base[180:205].mean()))


if __name__ == "__main__":
    unittest.main()
