"""#69 semantic hand-count delta around a NEW meld; synthetic only."""
from __future__ import annotations

from dataclasses import replace
import unittest

from workspace.vision.public_claim_hand_count_delta import (
    SourceScopedStableHandCount,
    review_new_meld_hand_count_delta,
)

SHA = "a" * 64


def sample(frame, count, **changes):
    data = {
        "source_session": "synthetic_original",
        "source_sha256": SHA,
        "stream_epoch": 4,
        "frame_index": frame,
        "actor": "player",
        "semantic_concealed_count": count,
        "tracker_state": "STABLE_HAND",
        "tracker_trusted": True,
        "tracker_stable": True,
        "hand_geometry_region_verified": True,
        "source_frame_verified": True,
        "draw_event_in_sample": False,
        "discard_event_in_sample": False,
        "hand_resort_or_occlusion_in_sample": False,
        "geometry_baseline_reset_in_sample": False,
        "evidence_ref": f"hand-count-frame:{frame}",
    }
    data.update(changes)
    return SourceScopedStableHandCount(**data)


def review(before, after, *, onset=101, faces=3, **kwargs):
    opts = {
        "new_meld_first_visible_frame": onset,
        "new_meld_face_count": faces,
        "pre_sample_brackets_onset": True,
        "post_sample_before_followup_discard": True,
        "independent_public_meld_onset_verified": True,
    }
    opts.update(kwargs)
    return review_new_meld_hand_count_delta(before, after, **opts)


class NewMeldHandCountDeltaTests(unittest.TestCase):
    def test_three_face_new_group_requires_exactly_two_removed(self):
        out = review(sample(100, 16), sample(102, 14), faces=3)
        self.assertEqual(
            out.status,
            "NEW_MELD_HAND_COUNT_DELTA_CORROBORATED_OWNER_ACTION_PENDING",
        )
        self.assertEqual(out.removed_count, 2)
        self.assertEqual(out.new_meld_face_count, 3)
        data = out.to_dict()
        self.assertFalse(data["concealed_hand_shadow_used"])
        self.assertTrue(data["semantic_count_only"])
        self.assertEqual(data["claim_action_kind"], "UNKNOWN")
        self.assertFalse(data["safe_for_runtime"])
        self.assertFalse(data["safe_for_executor"])
        self.assertNotIn(SHA, str(data))
        self.assertNotIn("synthetic_original", str(data))

    def test_four_face_new_group_requires_exactly_three_removed(self):
        out = review(sample(200, 16), sample(204, 13), onset=202, faces=4)
        self.assertEqual(
            out.status,
            "NEW_MELD_HAND_COUNT_DELTA_CORROBORATED_OWNER_ACTION_PENDING",
        )
        self.assertEqual(out.removed_count, 3)
        self.assertFalse(out.to_dict()["added_kong_supported"])

    def test_three_face_count_drop_does_not_classify_chi_or_peng(self):
        out = review(sample(10, 16), sample(12, 14), onset=11, faces=3)
        self.assertEqual(out.to_dict()["claim_action_kind"], "UNKNOWN")
        self.assertEqual(out.to_dict()["claimed_tile"], "UNKNOWN")

    def test_wrong_count_drop_is_conflict_not_guess(self):
        for after in (16, 15, 13, 12):
            with self.subTest(after=after):
                out = review(sample(100, 16), sample(102, after), faces=3)
                self.assertEqual(out.status, "CONFLICT")
                self.assertEqual(out.to_dict()["claim_action_kind"], "UNKNOWN")

    def test_four_face_existing_peng_upgrade_is_not_supported_by_new_group_gate(self):
        # Even a -1 count can be an ADD_KONG, but this NEW-group contract
        # intentionally rejects it rather than pretending it is Ming Gang.
        out = review(sample(100, 16), sample(102, 15), faces=4)
        self.assertEqual(out.status, "CONFLICT")
        self.assertFalse(out.to_dict()["added_kong_supported"])

    def test_draw_discard_resort_occlusion_or_baseline_reset_contaminates_sample(self):
        fields = (
            "draw_event_in_sample",
            "discard_event_in_sample",
            "hand_resort_or_occlusion_in_sample",
            "geometry_baseline_reset_in_sample",
        )
        for field in fields:
            with self.subTest(field=field):
                out = review(
                    sample(100, 16),
                    sample(102, 14, **{field: True}),
                    faces=3,
                )
                self.assertEqual(out.status, "UNKNOWN")
                self.assertIn("contaminated", out.reason)

    def test_tracker_and_geometry_must_be_source_verified_and_stable(self):
        for field, value in (
            ("tracker_trusted", False),
            ("tracker_stable", False),
            ("hand_geometry_region_verified", False),
            ("source_frame_verified", False),
            ("tracker_state", "DRAW_VISIBLE"),
            ("tracker_state", "HAND_RESORTING"),
        ):
            with self.subTest(field=field):
                out = review(
                    sample(100, 16),
                    sample(102, 14, **{field: value}),
                    faces=3,
                )
                self.assertEqual(out.status, "UNKNOWN")

    def test_source_sha_session_epoch_or_actor_change_abstains(self):
        for field, value in (
            ("source_session", "other"),
            ("source_sha256", "b" * 64),
            ("stream_epoch", 5),
            ("actor", "opponent"),
        ):
            with self.subTest(field=field):
                out = review(
                    sample(100, 16),
                    sample(102, 14, **{field: value}),
                    faces=3,
                )
                self.assertEqual(out.status, "UNKNOWN")

    def test_explicit_bracketing_and_meld_onset_are_mandatory(self):
        for kwargs in (
            {"pre_sample_brackets_onset": False},
            {"post_sample_before_followup_discard": False},
            {"independent_public_meld_onset_verified": False},
        ):
            with self.subTest(kwargs=kwargs):
                out = review(sample(100, 16), sample(102, 14), **kwargs)
                self.assertEqual(out.status, "UNKNOWN")
        self.assertEqual(
            review(sample(100, 16), sample(102, 14), onset=99).status,
            "UNKNOWN",
        )
        self.assertEqual(
            review(sample(100, 16), sample(102, 14), onset=103).status,
            "UNKNOWN",
        )

    def test_duplicate_evidence_reference_is_not_independent_delta(self):
        before = sample(100, 16, evidence_ref="same")
        after = sample(102, 14, evidence_ref="same")
        out = review(before, after)
        self.assertEqual(out.status, "UNKNOWN")
        self.assertIn("same_evidence", out.reason)

    def test_invalid_contract_values_fail_closed(self):
        for patch in (
            {"source_sha256": "bad"},
            {"stream_epoch": True},
            {"frame_index": -1},
            {"semantic_concealed_count": -1},
            {"actor": "unknown"},
            {"evidence_ref": ""},
        ):
            with self.subTest(patch=patch):
                out = review(sample(100, 16), sample(102, 14, **patch))
                self.assertEqual(out.status, "UNKNOWN")
        for faces in (2, 5, True):
            with self.subTest(faces=faces):
                self.assertEqual(
                    review(sample(100, 16), sample(102, 14), faces=faces).status,
                    "UNKNOWN",
                )


if __name__ == "__main__":
    unittest.main()
