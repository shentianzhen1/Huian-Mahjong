from __future__ import annotations

import unittest

from .geometry_schema import compatibility_view, new_geometry_row_fields


class GeometrySchemaTests(unittest.TestCase):
    def test_legacy_draw_migrates_only_in_memory(self) -> None:
        row = {
            "trust_state": "trusted",
            "components": [
                {"pixel_bbox": [1, 2, 3, 4], "region_candidate": "hand"},
                {"pixel_bbox": [9, 2, 3, 4], "region_candidate": "draw"},
            ],
            "expected_hand_component_count": 1,
        }
        view = compatibility_view(row)
        self.assertEqual(row["components"][1]["region_candidate"], "draw")
        self.assertEqual(view["components"][1]["region_candidate"], "draw_visual")
        self.assertEqual(view["expected_hand_region_count"], 1)
        self.assertEqual(view["expected_draw_visual_count"], 1)
        self.assertEqual(view["expected_concealed_tile_count"], 2)
        self.assertEqual(view["frame_state"], "trusted")

    def test_legacy_multiple_draws_are_preserved_and_warned(self) -> None:
        row = {"components": [
            {"pixel_bbox": [1, 1, 2, 2], "region_candidate": "draw"},
            {"pixel_bbox": [5, 1, 2, 2], "region_candidate": "draw"},
        ]}
        view = compatibility_view(row)
        self.assertEqual(view["expected_draw_visual_count"], 2)
        self.assertIn("draw_visual_count_outside_normal_0_or_1", view["schema_warnings"])

    def test_new_fields_derive_concealed_invariant(self) -> None:
        fields = new_geometry_row_fields([
            {"pixel_bbox": [1, 1, 2, 2], "region_candidate": "hand"},
            {"pixel_bbox": [5, 1, 2, 2], "region_candidate": "draw_visual"},
            {"pixel_bbox": [9, 1, 2, 2], "region_candidate": "gold"},
        ], "trusted")
        self.assertEqual(fields["expected_hand_region_count"], 1)
        self.assertEqual(fields["expected_draw_visual_count"], 1)
        self.assertEqual(fields["expected_concealed_tile_count"], 2)

    def test_non_game_scene_is_explicit_and_has_no_concealed_tiles(self) -> None:
        fields = new_geometry_row_fields([], "non_game", scene_type="settlement")
        self.assertEqual(fields["frame_state"], "non_game")
        self.assertEqual(fields["scene_type"], "settlement")
        self.assertIsNone(fields["animation_type"])
        self.assertEqual(fields["expected_concealed_tile_count"], 0)


if __name__ == "__main__":
    unittest.main()
