from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from PIL import Image, ImageDraw

from .gold_skin_review_queue import (
    GoldReviewCandidate,
    _dedupe_candidates,
    _validate_private_output,
    propose_gold_skin_candidates,
)


def two_gold_frame() -> Image.Image:
    image = Image.new("RGB", (1000, 480), (0, 55, 55))
    draw = ImageDraw.Draw(image)
    for index in range(16):
        x = 100 + index * 45
        colour = (230, 200, 50) if index == 0 else "white"
        draw.rectangle((x, 400, x + 40, 470), fill=colour)
    draw.rectangle((880, 400, 920, 470), fill=(230, 200, 50))
    return image


class FixedGoldClassifier:
    def classify_gold_skin(self, crop):
        return SimpleNamespace(tile_id="M6", confidence=0.71)


class GoldSkinReviewQueueTests(unittest.TestCase):
    def test_two_real_geometry_gold_slots_become_review_only_candidates(self):
        candidates = propose_gold_skin_candidates(
            two_gold_frame(),
            FixedGoldClassifier(),
            frame_id=3300,
            seconds=110.0,
            source_session="session_match_a",
        )
        self.assertEqual(len(candidates), 2)
        self.assertEqual(
            {candidate.region for candidate in candidates},
            {"hand_region", "draw_visual"},
        )
        for candidate in candidates:
            self.assertEqual(candidate.candidate_tile_id, "M6")
            metadata = candidate.metadata()
            self.assertEqual(metadata["status"], "proposed")
            self.assertFalse(metadata["approved"])
            self.assertTrue(metadata["review_required"])
            self.assertFalse(metadata["safe_for_hint"])
            self.assertFalse(metadata["safe_for_executor"])

    def test_dedupe_keeps_highest_confidence_per_physical_slot(self):
        image = Image.new("RGB", (40, 70), "white")
        low = GoldReviewCandidate(
            100, 10.0, "hand_region", (100, 400, 40, 70),
            (98, 390, 44, 78), "M6", 0.55, image,
        )
        high = GoldReviewCandidate(
            101, 10.1, "hand_region", (101, 400, 40, 70),
            (99, 390, 44, 78), "M6", 0.72, image,
        )
        other = GoldReviewCandidate(
            101, 10.1, "draw_visual", (880, 400, 40, 70),
            (878, 390, 44, 78), "M6", 0.68, image,
        )
        deduped = _dedupe_candidates([low, high, other], frame_width=1000)
        self.assertEqual(len(deduped), 2)
        self.assertIn(high, deduped)
        self.assertIn(other, deduped)
        self.assertNotIn(low, deduped)

    def test_private_queue_output_is_rejected_inside_git_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            with self.assertRaisesRegex(ValueError, "outside the Git repository"):
                _validate_private_output(
                    root / "private_review",
                    working_dir=root,
                )

    def test_private_queue_output_is_allowed_outside_repository(self):
        with tempfile.TemporaryDirectory() as repository, tempfile.TemporaryDirectory() as outside:
            root = Path(repository)
            (root / ".git").mkdir()
            _validate_private_output(
                Path(outside) / "gold_review",
                working_dir=root,
            )


if __name__ == "__main__":
    unittest.main()
