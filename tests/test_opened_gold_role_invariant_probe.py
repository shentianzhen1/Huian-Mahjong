import importlib.util
import unittest

from workspace.vision.tiles_runtime_v0_2.opened_gold_role_invariant_probe import (
    choose_role_invariant_candidate,
    tile_family,
)


class OpenedGoldRoleInvariantProbeTests(unittest.TestCase):
    def test_tile_family(self):
        self.assertEqual(tile_family("M6"), "M")
        self.assertEqual(tile_family("P9"), "P")
        self.assertEqual(tile_family("S3"), "S")
        self.assertEqual(tile_family("N"), "H")
        self.assertEqual(tile_family("SOUTH"), "H")

    def test_clear_glyph_margin_overrides_full_face_inside_family(self):
        result = choose_role_invariant_candidate(
            {"M1": 0.66, "M6": 0.62, "P9": 0.30},
            {"M1": 0.50, "M6": 0.55, "P9": 0.90},
            glyph_margin=0.03,
        )
        self.assertEqual(result["family"], "M")
        self.assertEqual(result["candidate_tile"], "M6")
        self.assertEqual(result["decision_feature"], "glyph")
        self.assertFalse(result["scores_are_runtime_confidence"])
        self.assertFalse(result["safe_for_runtime"])

    def test_ambiguous_glyph_falls_back_to_full_face(self):
        result = choose_role_invariant_candidate(
            {"M7": 0.68, "M6": 0.67, "P9": 0.20},
            {"M7": 0.60, "M6": 0.61, "P9": 0.95},
            glyph_margin=0.03,
        )
        self.assertEqual(result["family"], "M")
        self.assertEqual(result["candidate_tile"], "M7")
        self.assertEqual(result["decision_feature"], "full_face")

    def test_family_gate_prevents_cross_family_glyph_override(self):
        result = choose_role_invariant_candidate(
            {"M6": 0.70, "M7": 0.65, "P9": 0.40, "P5": 0.39},
            {"M6": 0.51, "M7": 0.50, "P9": 0.99, "P5": 0.10},
            glyph_margin=0.0,
        )
        self.assertEqual(result["family"], "M")
        self.assertEqual(result["candidate_tile"], "M6")

    def test_invalid_or_empty_scores_fail_closed(self):
        empty = choose_role_invariant_candidate({}, {})
        self.assertIsNone(empty["candidate_tile"])
        with self.assertRaises(ValueError):
            choose_role_invariant_candidate(
                {"M6": 1.0}, {"M6": 1.0}, glyph_margin=-0.1
            )

    @unittest.skipUnless(
        importlib.util.find_spec("numpy") is not None
        and importlib.util.find_spec("cv2") is not None
        and importlib.util.find_spec("PIL") is not None,
        "Vision dependencies not installed",
    )
    def test_image_features_are_finite_when_vision_deps_exist(self):
        import numpy as np
        from PIL import Image, ImageDraw
        from workspace.vision.tiles_runtime_v0_2.opened_gold_role_invariant_probe import (
            _appearance_maps,
            _glyph_maps,
        )

        image = Image.new("RGB", (40, 64), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((10, 12, 29, 50), outline="black", width=3)
        draw.ellipse((15, 20, 25, 30), fill="red")
        full = _appearance_maps(image)
        glyph = _glyph_maps(image)
        self.assertEqual(full.shape, (4, 96, 64))
        self.assertEqual(glyph.shape, (4, 96, 64))
        self.assertTrue(np.isfinite(full).all())
        self.assertTrue(np.isfinite(glyph).all())


if __name__ == "__main__":
    unittest.main()
