import importlib.util
import unittest
from workspace.vision.public_meld_bracketed_front_band_probe import (
    prepare_bracketed_front_band, build_peer_contexts, prepare_from_peer_context)

VISION = all(importlib.util.find_spec(name) is not None for name in ("PIL", "cv2", "numpy"))
if VISION:
    from PIL import Image, ImageDraw


@unittest.skipUnless(VISION, "optional Vision dependencies")
class BracketedFrontBandTests(unittest.TestCase):
    def face(self, shadow=False):
        image = Image.new("RGB", (60, 90), (140, 140, 140) if shadow else (180, 180, 180))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 59, 54), fill=(145, 145, 145) if shadow else (245, 245, 245))
        draw.rectangle((17, 6, 38, 15), fill=(10, 10, 10))
        draw.rectangle((18, 30, 40, 47), fill=(160, 0, 0))
        return image

    def test_shadowed_middle_uses_geometry_and_preserves_glyph(self):
        result, audit = prepare_bracketed_front_band(self.face(True), (60, 0, 120, 90),
            [(self.face(), (0, 0, 60, 90)), (self.face(), (120, 0, 180, 90))])
        self.assertIsNotNone(result)
        self.assertEqual(audit["reason"], "bracketed_geometry_candidate")
        self.assertFalse(audit["raw_feature_fallback"])
        self.assertEqual(result.getpixel((30, 45)), (160, 0, 0))
        self.assertFalse(audit["safe_for_runtime"])

    def test_missing_peer_or_edge_target_cannot_extrapolate(self):
        for peers in ([], [(self.face(), (0, 0, 60, 90))],
                      [(self.face(), (0, 0, 60, 90)), (self.face(), (0, 0, 60, 90))]):
            result, audit = prepare_bracketed_front_band(self.face(True), (60, 0, 120, 90), peers)
            self.assertIsNone(result)
            self.assertEqual(audit["reason"], "no_unique_left_right_bracket")

    def test_unrelated_or_distant_row_cannot_supply_boundary(self):
        for peers in (
            [(self.face(), (0, 1, 60, 91)), (self.face(), (120, 0, 180, 90))],
            [(self.face(), (0, 0, 60, 90)), (self.face(), (180, 0, 240, 90))]):
            self.assertIsNone(prepare_bracketed_front_band(self.face(True), (60, 0, 120, 90), peers)[0])

    def test_mismatched_pixel_bounds_are_rejected(self):
        with self.assertRaises(ValueError):
            prepare_bracketed_front_band(self.face(True), (60, 0, 119, 90), [])

    def test_sloping_peer_boundaries_require_rectification(self):
        short = self.face()
        ImageDraw.Draw(short).rectangle((0, 30, 59, 89), fill=(180, 180, 180))
        result, audit = prepare_bracketed_front_band(self.face(True), (60, 0, 120, 90),
            [(short, (0, 0, 60, 90)), (self.face(), (120, 0, 180, 90))])
        self.assertIsNone(result)
        self.assertEqual(audit["reason"], "peer_boundary_slope_requires_rectification")

    def group(self):
        return [(dict(query_id=str(i), source_sha256="source", source_frame_pin=1,
                      original_match_group="match", bounds=[60*i, 0, 60*(i+1), 90]),
                 self.face(i == 1)) for i in range(3)]

    def test_context_cannot_cross_source_frame_or_match(self):
        for field in ("source_sha256", "source_frame_pin", "original_match_group"):
            group = self.group()
            group[2][0][field] = "other"
            with self.assertRaises(ValueError):
                build_peer_contexts([group])

    def test_ambiguous_or_missing_pixel_context_does_not_borrow_peers(self):
        group = self.group()
        for contexts in ({}, build_peer_contexts([group, group])):
            result, audit = prepare_from_peer_context(self.face(True), contexts, query_id="1", source_sha256="source")
            self.assertIsNone(result)
            self.assertEqual(audit["peer_context_status"], "missing_or_ambiguous")

    def test_equal_pixels_cannot_borrow_a_different_source_or_row(self):
        contexts = build_peer_contexts([self.group()])
        for query, source in (("1", "other-source"), ("other-row", "source"), (None, None)):
            result, audit = prepare_from_peer_context(self.face(True), contexts,
                query_id=query, source_sha256=source)
            self.assertIsNone(result)
        result, audit = prepare_from_peer_context(self.face(True), contexts,
            query_id="1", source_sha256="source")
        self.assertIsNotNone(result)
        self.assertEqual(audit["verified_source_frame_pin"], 1)

    def test_valid_direct_candidate_needs_no_peers(self):
        result, audit = prepare_bracketed_front_band(self.face(), (60, 0, 120, 90), [])
        self.assertIsNotNone(result)
        self.assertEqual(audit["reason"], "direct_front_band")


if __name__ == "__main__":
    unittest.main()
