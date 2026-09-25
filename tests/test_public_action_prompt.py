"""#69 system-prompt offer contracts: no concealed-hand shade dependency."""
from __future__ import annotations

from dataclasses import replace
import unittest

from workspace.vision.public_action_prompt import (
    PublicActionPromptFrame, review_system_prompt,
)

SHA = "a" * 64


def frame(index=100, labels=("吃", "过"), **overrides):
    values = dict(
        source_session="synthetic_original",
        source_sha256=SHA,
        stream_epoch=3,
        frame_index=index,
        buttons_left_to_right=labels,
        source_frame_verified=True,
        action_button_region_verified=True,
        live_interactive_view_verified=True,
        independently_verified_capture_mode="LIVE_INTERACTIVE",
        capture_mode_verified_without_buttons=True,
    )
    values.update(overrides)
    return PublicActionPromptFrame(**values)


class PublicSystemActionPromptTests(unittest.TestCase):
    def test_chi_peng_kong_hu_are_offered_only_not_actions(self):
        for name, expected in (("吃", "CHI"), ("碰", "PENG"),
                               ("杠", "KONG"), ("胡", "HU")):
            with self.subTest(name=name):
                result = review_system_prompt([
                    frame(100, (name, "过")), frame(101, (name, "过")),
                ])
                self.assertEqual(result.status, "STABLE_OFFERED_ACTIONS_NOT_EXECUTED")
                self.assertEqual(result.offered_actions, (expected, "PASS")
                                 if expected < "PASS" else ("PASS", expected))
                payload = result.to_dict()
                self.assertFalse(payload["hand_shadow_used"])
                self.assertEqual(payload["executed_action"], "UNKNOWN")
                self.assertEqual(payload["claimed_tile"], "UNKNOWN")
                self.assertFalse(payload["safe_for_runtime"])
                self.assertFalse(payload["safe_for_executor"])
                self.assertNotIn(SHA, str(payload))

    def test_multiple_available_actions_are_not_assumed_selected(self):
        out = review_system_prompt([
            frame(100, ("吃", "碰", "杠", "胡", "过")),
            frame(101, ("过", "胡", "杠", "碰", "吃")),
        ])
        self.assertEqual(out.status, "STABLE_OFFERED_ACTIONS_NOT_EXECUTED")
        self.assertEqual(set(out.offered_actions),
                         {"CHI", "PENG", "KONG", "HU", "PASS"})
        self.assertEqual(out.to_dict()["executed_action"], "UNKNOWN")

    def test_no_prompt_cannot_mean_auto_draw(self):
        out = review_system_prompt([frame(100, ()), frame(101, ())])
        self.assertEqual(out.status, "NO_PROMPT_OBSERVED")
        self.assertEqual(out.offered_actions, ())
        self.assertTrue(out.to_dict()["draw_requires_independent_draw_visual_transition"])

    def test_replay_overlay_is_not_a_live_claim_button(self):
        # The owner's screenshot shows a replay transport overlay; an
        # apparently visible PASS icon must not become a live prompt.
        out = review_system_prompt([
            frame(100, ("过", "吃"), replay_controls_visible=True),
            frame(101, ("过", "吃"), replay_controls_visible=True),
        ])
        self.assertEqual(out.status, "UNKNOWN")
        self.assertIn("replay_overlay", out.issues[0])

    def test_non_live_lookalikes_and_unverified_rois_abstain(self):
        for key in (
            "live_interactive_view_verified",
            "source_frame_verified",
            "action_button_region_verified",
        ):
            with self.subTest(key=key):
                out = review_system_prompt([
                    frame(100), frame(101, **{key: False}),
                ])
                self.assertEqual(out.status, "UNKNOWN")
        self.assertEqual(review_system_prompt([
            frame(100), frame(101, obscuring_overlay_visible=True),
        ]).status, "UNKNOWN")

    def test_unknown_or_replay_capture_mode_never_trains_live_prompt(self):
        # Every one of nine existing original clips includes a replay
        # transport overlay at its source-video mid-frame. Positive live
        # button evidence requires independently verified LIVE provenance.
        for attrs in (
            {"independently_verified_capture_mode": "UNKNOWN"},
            {"independently_verified_capture_mode": "IN_GAME_REPLAY"},
            {"capture_mode_verified_without_buttons": False},
            {"independently_verified_capture_mode": "LIVE_INTERACTIVE",
             "capture_mode_verified_without_buttons": False},
        ):
            with self.subTest(attrs=attrs):
                out = review_system_prompt([
                    frame(100, ("吃", "过"), **attrs),
                    frame(101, ("吃", "过"), **attrs),
                ])
                self.assertEqual(out.status, "UNKNOWN")
                self.assertEqual(out.to_dict()["executed_action"], "UNKNOWN")
        live = review_system_prompt([
            frame(100, ("吃", "过")), frame(101, ("吃", "过")),
        ])
        self.assertEqual(live.status, "STABLE_OFFERED_ACTIONS_NOT_EXECUTED")

    def test_mo_is_not_assumed_to_be_a_claim_button(self):
        # Ordinary draw needs physical draw_visual evidence.
        for labels in (("摸",), ("摸", "吃", "过")):
            with self.subTest(labels=labels):
                out = review_system_prompt([
                    frame(100, labels), frame(101, labels),
                ])
                self.assertEqual(out.status, "UNKNOWN")
                self.assertEqual(out.to_dict()["executed_action"], "UNKNOWN")

    def test_unstable_single_frame_or_changed_actions_abstain(self):
        self.assertEqual(review_system_prompt([frame()]).status, "UNKNOWN")
        self.assertEqual(review_system_prompt([
            frame(100, ("吃", "过")), frame(101, ("碰", "过")),
        ]).status, "UNKNOWN")
        self.assertEqual(review_system_prompt([
            frame(100), frame(101),
        ], min_stable_frames=3).status, "UNKNOWN")

    def test_source_session_sha_epoch_or_frame_gap_abstains(self):
        for field, replacement in (
            ("source_session", "other_source"),
            ("source_sha256", "b" * 64),
            ("stream_epoch", 4),
            ("frame_index", 103),
        ):
            with self.subTest(field=field):
                out = review_system_prompt([
                    frame(100), replace(frame(101), **{field: replacement}),
                ])
                self.assertEqual(out.status, "UNKNOWN")
        self.assertEqual(review_system_prompt([
            frame(100, source_sha256="not_sha"), frame(101),
        ]).status, "UNKNOWN")

    def test_pass_only_does_not_establish_claim(self):
        out = review_system_prompt([
            frame(100, ("过",)), frame(101, ("过",)),
        ])
        self.assertEqual(out.status, "UNKNOWN")
        self.assertEqual(out.to_dict()["executed_action"], "UNKNOWN")

    def test_invalid_duplicate_labels_and_wrong_types_abstain(self):
        for labels in (("吃", "吃", "过"), ("吃", "UNKNOWN"),
                       ("吃", "过", "摸"), ["吃", "过"]):
            with self.subTest(labels=labels):
                out = review_system_prompt([
                    frame(100, labels), frame(101, labels),
                ])
                self.assertEqual(out.status, "UNKNOWN")

    def test_stable_three_frames_and_invalid_stability_parameters(self):
        out = review_system_prompt([
            frame(100), frame(101), frame(102),
        ], min_stable_frames=3)
        self.assertEqual(out.status, "STABLE_OFFERED_ACTIONS_NOT_EXECUTED")
        for invalid in (True, 1, 0, -2):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    review_system_prompt([frame(100), frame(101)],
                                         min_stable_frames=invalid)


if __name__ == "__main__":
    unittest.main()
