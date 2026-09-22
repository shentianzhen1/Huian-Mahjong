from __future__ import annotations

import json
from pathlib import Path
import unittest

from PIL import Image, ImageDraw

from workspace.vision.dealer_marker_detector import (
    DealerMarkerProfile,
    detect_dealer_marker,
)


ROOT = Path(__file__).resolve().parents[3]
CALIBRATION = (
    ROOT
    / "references"
    / "vision"
    / "2026-09-22"
    / "public_detector_calibration_v0_1.json"
)


class DealerMarkerDetectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        data = json.loads(CALIBRATION.read_text(encoding="utf-8"))
        cls.samples = tuple(
            row
            for row in data["samples"]
            if row["target"] in {"discard", "meld"}
        )

    def test_two_real_sessions_have_opposite_dealer_anchors(self):
        failures = []
        for row in self.samples:
            image = Image.open(ROOT / row["image_path"]).convert("RGB")
            observed = detect_dealer_marker(
                image,
                frame=row["frame_index"],
                session=row["source_session"],
            )
            expected = (
                "opponent"
                if row["source_session"] == "66fe863f_youjin100"
                else "player"
            )
            if observed.actor != expected:
                failures.append(
                    (
                        row["sample_id"],
                        expected,
                        observed.actor,
                        observed.player_signal.to_dict(),
                        observed.opponent_signal.to_dict(),
                    )
                )
            self.assertFalse(observed.safe_for_hint)
            self.assertFalse(observed.safe_for_executor)
            self.assertTrue(observed.evidence_refs)

        self.assertEqual(failures, [])

    def test_real_positive_marker_has_margin_over_inactive_side(self):
        for row in self.samples:
            image = Image.open(ROOT / row["image_path"]).convert("RGB")
            observed = detect_dealer_marker(image)
            self.assertIsNotNone(observed.actor, row["sample_id"])
            active = (
                observed.player_signal
                if observed.actor == "player"
                else observed.opponent_signal
            )
            inactive = (
                observed.opponent_signal
                if observed.actor == "player"
                else observed.player_signal
            )
            self.assertGreaterEqual(active.mask_ratio, 0.05)
            self.assertGreaterEqual(active.largest_component_ratio, 0.035)
            self.assertLess(inactive.mask_ratio, 0.01)
            self.assertLess(inactive.largest_component_ratio, 0.01)

    def test_half_resolution_preserves_actor(self):
        rows = (
            next(
                row
                for row in self.samples
                if row["sample_id"] == "66fe_opponent_discard_p1_035s"
            ),
            next(
                row
                for row in self.samples
                if row["sample_id"] == "b389_opponent_discard_m4_033s"
            ),
        )
        for row in rows:
            image = Image.open(ROOT / row["image_path"]).convert("RGB")
            half = image.resize(
                (image.width // 2, image.height // 2),
                Image.Resampling.LANCZOS,
            )
            full_result = detect_dealer_marker(image)
            half_result = detect_dealer_marker(half)
            self.assertEqual(half_result.actor, full_result.actor)

    def test_blank_frame_is_unknown(self):
        image = Image.new("RGB", (1046, 480), (20, 100, 90))
        observed = detect_dealer_marker(image)
        self.assertIsNone(observed.actor)
        self.assertEqual(observed.issues, ("dealer_marker_unreadable",))
        self.assertEqual(observed.confidence, 0.0)

    def test_both_active_zones_fail_closed(self):
        image = Image.new("RGB", (1046, 480), (20, 100, 90))
        draw = ImageDraw.Draw(image)
        profile = DealerMarkerProfile()
        for box in (profile.player_marker, profile.opponent_marker):
            left, top, right, bottom = box.pixel_box(image.size)
            draw.rectangle(
                (
                    left + 3,
                    top + 3,
                    max(left + 8, right - 3),
                    max(top + 8, bottom - 3),
                ),
                fill=(255, 70, 0),
            )
        observed = detect_dealer_marker(image, profile=profile)
        self.assertIsNone(observed.actor)
        self.assertEqual(observed.issues, ("dealer_marker_ambiguous",))

    def test_marker_maps_to_dealer_seat_only_with_explicit_player_seat(self):
        row = next(
            row
            for row in self.samples
            if row["sample_id"] == "66fe_opponent_discard_p1_035s"
        )
        image = Image.open(ROOT / row["image_path"]).convert("RGB")
        observed = detect_dealer_marker(
            image,
            frame=row["frame_index"],
            session=row["source_session"],
        )
        self.assertEqual(observed.actor, "opponent")

        unknown_seat = observed.to_dealer_evidence(
            timestamp_seconds=1.0,
            player_seat=None,
        )
        self.assertIsNone(unknown_seat.dealer_seat)

        player_zero = observed.to_dealer_evidence(
            timestamp_seconds=1.0,
            player_seat=0,
        )
        self.assertEqual(player_zero.dealer_seat, 1)

        player_one = observed.to_dealer_evidence(
            timestamp_seconds=1.0,
            player_seat=1,
        )
        self.assertEqual(player_one.dealer_seat, 0)

    def test_detector_does_not_expose_dealer_count_or_base(self):
        row = next(
            row
            for row in self.samples
            if row["sample_id"] == "b389_opponent_discard_m4_033s"
        )
        image = Image.open(ROOT / row["image_path"]).convert("RGB")
        payload = detect_dealer_marker(image).to_dict()
        self.assertEqual(payload["actor"], "player")
        self.assertNotIn("dealer_count", payload)
        self.assertNotIn("dealer_base", payload)


if __name__ == "__main__":
    unittest.main()
