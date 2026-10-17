import unittest
from dataclasses import replace

from workspace.vision.public_claim_hand_count_delta import (
    SourceScopedStableHandCount, review_new_meld_hand_count_delta,
)
from workspace.vision.public_hand_identity_delta import (
    StableHandIdentitySnapshot, review_hand_identity_delta,
    review_hand_identity_delta_with_intervening_draw,
)

SHA = "a" * 64


def count_sample(frame, count):
    return SourceScopedStableHandCount(
        "s", SHA, 0, frame, "player", count, "STABLE_HAND",
        True, True, True, True, evidence_ref=f"count:{frame}",
    )


def snap(frame, tiles, confidence=0.90):
    return StableHandIdentitySnapshot(
        "s", SHA, 0, frame, "player", tuple(tiles), confidence, 0.82,
        True, True, True, True, f"identity:{frame}",
    )


def count_review():
    return review_new_meld_hand_count_delta(
        count_sample(100, 16), count_sample(102, 13),
        new_meld_first_visible_frame=101, new_meld_face_count=4,
        pre_sample_brackets_onset=True,
        post_sample_before_followup_discard=True,
        independent_public_meld_onset_verified=True,
    )


class PublicHandIdentityDeltaTests(unittest.TestCase):
    def test_three_p6_removed_is_identity_qualified(self):
        before = snap(100, ["P6","P6","P6","M1","M2"])
        after = snap(102, ["M1","M2"])
        out = review_hand_identity_delta(before, after, count_review())
        self.assertEqual(out.status, "IDENTITY_QUALIFIED_HAND_DELTA")
        self.assertEqual(out.removed_tiles, ("P6","P6","P6"))
        self.assertFalse(out.to_dict()["safe_for_runtime"])
        self.assertFalse(out.to_dict()["safe_for_executor"])

    def test_replacement_draw_can_be_accounted_without_guessing(self):
        before = snap(100, ["P6","P6","P6","M1","M2"])
        after = snap(103, ["M1","M2","M3"])
        out = review_hand_identity_delta_with_intervening_draw(
            before, after, count_review(), intervening_draw_tiles=("M3",),
        )
        self.assertEqual(out.status, "IDENTITY_QUALIFIED_HAND_DELTA")
        self.assertEqual(out.removed_tiles, ("P6","P6","P6"))
        self.assertIn("intervening_draw", out.reason)

    def test_replacement_draw_must_be_independently_observed(self):
        out = review_hand_identity_delta_with_intervening_draw(
            snap(100, ["P6","P6","P6","M1","M2"]),
            snap(103, ["M1","M2","M3"]),
            count_review(), intervening_draw_tiles=(),
        )
        self.assertEqual(out.status, "UNKNOWN")
        self.assertIn("not_observed", out.reason)

    def test_below_threshold_abstains(self):
        out = review_hand_identity_delta(
            snap(100, ["P6","P6","P6","M1","M2"], 0.81),
            snap(102, ["M1","M2"]), count_review(),
        )
        self.assertEqual(out.status, "UNKNOWN")
        self.assertIn("threshold", out.reason)

    def test_count_identity_disagreement_abstains(self):
        out = review_hand_identity_delta(
            snap(100, ["P6","P6","M1","M2"]),
            snap(102, ["M1","M2"]), count_review(),
        )
        self.assertEqual(out.status, "UNKNOWN")
        self.assertIn("disagrees", out.reason)

    def test_unexplained_added_tile_abstains(self):
        out = review_hand_identity_delta(
            snap(100, ["P6","P6","P6","M1","M2"]),
            snap(102, ["M1","M2","S1"]), count_review(),
        )
        self.assertEqual(out.status, "UNKNOWN")
        self.assertIn("added", out.reason)

    def test_cross_source_abstains(self):
        after = replace(snap(102, ["M1","M2"]), source_sha256="b"*64)
        out = review_hand_identity_delta(
            snap(100, ["P6","P6","P6","M1","M2"]), after, count_review(),
        )
        self.assertEqual(out.status, "UNKNOWN")
        self.assertIn("source", out.reason)


if __name__ == "__main__":
    unittest.main()
