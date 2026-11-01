"""Pure streaming #69 system-prompt tests; no actual game or private video in CI."""
from __future__ import annotations

from dataclasses import replace
import unittest

from workspace.vision.public_action_prompt import PublicActionPromptFrame
from workspace.vision.public_prompt_window_tracker import SystemPromptWindowTracker

SHA = "a" * 64


def ui(frame_index, buttons=("吃", "过"), **changes):
    data = {
        "source_session": "synthetic_live_match",
        "source_sha256": SHA,
        "stream_epoch": 3,
        "frame_index": frame_index,
        "buttons_left_to_right": buttons,
        "source_frame_verified": True,
        "action_button_region_verified": True,
        "live_interactive_view_verified": True,
        "replay_controls_visible": False,
        "obscuring_overlay_visible": False,
        "independently_verified_capture_mode": "LIVE_INTERACTIVE",
        "capture_mode_verified_without_buttons": True,
    }
    data.update(changes)
    return PublicActionPromptFrame(**data)


def collect(tracker, frames):
    return tuple(
        transition
        for frame in frames
        for transition in tracker.observe(frame)
    )


class SystemPromptWindowTrackerTests(unittest.TestCase):
    def test_stable_open_once_and_no_repeat_per_frame(self):
        tracker = SystemPromptWindowTracker()
        out = collect(tracker, [ui(10), ui(11), ui(12), ui(13)])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].status, "PROMPT_OPENED")
        self.assertEqual(out[0].window_id, 1)
        self.assertEqual(out[0].offered_actions, ("CHI", "PASS"))
        self.assertEqual((out[0].first_frame, out[0].last_frame), (10, 11))
        data = out[0].to_dict()
        self.assertFalse(data["hand_shadow_used"])
        self.assertEqual(data["action_selection"], "UNKNOWN")
        self.assertEqual(data["pass_selected"], "UNKNOWN")
        self.assertEqual(data["draw_event"], "UNKNOWN")
        self.assertFalse(data["safe_for_runtime"])
        self.assertFalse(data["safe_for_executor"])
        self.assertNotIn(SHA, str(data))
        self.assertNotIn("synthetic_live_match", str(data))

    def test_stable_new_choices_update_existing_window_not_action(self):
        tracker = SystemPromptWindowTracker()
        out = collect(tracker, [
            ui(10), ui(11),
            ui(12, ("杠", "碰", "过")),
            ui(13, ("过", "碰", "杠")),
        ])
        self.assertEqual([x.status for x in out],
                         ["PROMPT_OPENED", "PROMPT_OPTIONS_CHANGED"])
        self.assertEqual(out[1].window_id, out[0].window_id)
        self.assertEqual(out[1].previous_actions, ("CHI", "PASS"))
        self.assertEqual(out[1].offered_actions, ("KONG", "PASS", "PENG"))
        self.assertEqual(out[1].to_dict()["action_selection"], "UNKNOWN")

    def test_stable_disappearance_is_not_pass_draw_or_claim(self):
        tracker = SystemPromptWindowTracker()
        out = collect(tracker, [
            ui(20), ui(21),
            ui(22, ()), ui(23, ()),
        ])
        self.assertEqual(
            [x.status for x in out],
            ["PROMPT_OPENED", "PROMPT_DISAPPEARED_UNATTRIBUTED"],
        )
        last = out[-1].to_dict()
        self.assertEqual(last["pass_selected"], "UNKNOWN")
        self.assertEqual(last["draw_event"], "UNKNOWN")
        self.assertEqual(last["action_selection"], "UNKNOWN")
        self.assertEqual(out[-1].previous_actions, ("CHI", "PASS"))
        out2 = collect(tracker, [ui(24), ui(25)])
        self.assertEqual(out2[0].window_id, 2)

    def test_single_missing_frame_or_flicker_does_not_close(self):
        tracker = SystemPromptWindowTracker()
        out = collect(tracker, [
            ui(10), ui(11), ui(12, ()), ui(13),
            ui(14, ()), ui(15),
        ])
        self.assertEqual([x.status for x in out], ["PROMPT_OPENED"])

    def test_no_prompt_or_pass_only_is_not_a_confirmed_draw(self):
        tracker = SystemPromptWindowTracker()
        self.assertEqual(
            collect(tracker, [ui(10, ()), ui(11, ())]), (),
        )
        self.assertEqual(
            collect(tracker, [ui(12, ("过",)), ui(13, ("过",))]), (),
        )
        out = collect(tracker, [ui(14), ui(15), ui(16, ("过",)),
                                ui(17, ("过",))])
        self.assertEqual(out[0].status, "PROMPT_OPENED")
        self.assertEqual(out[1].status, "PROMPT_INTERRUPTED_UNKNOWN")
        self.assertEqual(out[1].to_dict()["pass_selected"], "UNKNOWN")

    def test_replay_source_is_an_invalid_positive_even_with_button_labels(self):
        tracker = SystemPromptWindowTracker()
        self.assertEqual(collect(tracker, [
            ui(100, independently_verified_capture_mode="IN_GAME_REPLAY",
               live_interactive_view_verified=False,
               replay_controls_visible=True),
            ui(101, independently_verified_capture_mode="IN_GAME_REPLAY",
               live_interactive_view_verified=False,
               replay_controls_visible=True),
        ]), ())
        out = collect(tracker, [ui(102), ui(103)])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].status, "PROMPT_OPENED")

    def test_gallery_overlay_interrupts_offer_without_action_completion(self):
        tracker = SystemPromptWindowTracker()
        out = collect(tracker, [
            ui(100), ui(101),
            ui(102, replay_controls_visible=True),
            ui(103), ui(104),
        ])
        self.assertEqual(
            [x.status for x in out],
            ["PROMPT_OPENED", "PROMPT_INTERRUPTED_UNKNOWN", "PROMPT_OPENED"],
        )
        self.assertEqual(out[-1].window_id, 2)
        self.assertEqual(out[1].to_dict()["action_selection"], "UNKNOWN")

    def test_session_epoch_or_sha_change_interrupts_without_linking_sources(self):
        for name, value in (
            ("source_session", "new_match"),
            ("source_sha256", "b" * 64),
            ("stream_epoch", 4),
        ):
            with self.subTest(name=name):
                tracker = SystemPromptWindowTracker()
                first = collect(tracker, [ui(100), ui(101)])
                changed = collect(tracker, [
                    ui(0, **{name: value}),
                    ui(1, **{name: value}),
                ])
                self.assertEqual(first[0].status, "PROMPT_OPENED")
                self.assertEqual(changed[0].status, "PROMPT_INTERRUPTED_UNKNOWN")
                self.assertEqual(changed[1].status, "PROMPT_OPENED")
                self.assertEqual(changed[1].window_id, 2)

    def test_frame_gap_duplicate_or_out_of_order_interrupts_and_restarts(self):
        for index in (101, 99, 104):
            with self.subTest(index=index):
                tracker = SystemPromptWindowTracker()
                collect(tracker, [ui(100), ui(101)])
                out = tracker.observe(ui(index))
                self.assertEqual(len(out), 1)
                self.assertEqual(out[0].status, "PROMPT_INTERRUPTED_UNKNOWN")
                self.assertEqual(
                    collect(tracker, [ui(index + 1)])[0].status,
                    "PROMPT_OPENED",
                )

    def test_invalid_unknown_source_cannot_preserve_active_window(self):
        tracker = SystemPromptWindowTracker()
        collect(tracker, [ui(100), ui(101)])
        out = tracker.observe(ui(102, source_sha256="bad-sha"))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].status, "PROMPT_INTERRUPTED_UNKNOWN")
        self.assertEqual(out[0].to_dict()["action_selection"], "UNKNOWN")

    def test_unverified_roi_and_capture_mode_provenance_interrupt(self):
        for change in (
            {"source_frame_verified": False},
            {"action_button_region_verified": False},
            {"capture_mode_verified_without_buttons": False},
            {"independently_verified_capture_mode": "UNKNOWN"},
            {"obscuring_overlay_visible": True},
        ):
            with self.subTest(change=change):
                tracker = SystemPromptWindowTracker()
                collect(tracker, [ui(100), ui(101)])
                out = tracker.observe(ui(102, **change))
                self.assertEqual(out[0].status, "PROMPT_INTERRUPTED_UNKNOWN")

    def test_invalid_duplicate_unexpected_or_mo_button_never_commits(self):
        for buttons in (("摸", "过"), ("吃", "吃"), ["吃", "过"]):
            with self.subTest(buttons=buttons):
                tracker = SystemPromptWindowTracker()
                collect(tracker, [ui(100), ui(101)])
                out = tracker.observe(ui(102, buttons))
                self.assertEqual(out[0].status, "PROMPT_INTERRUPTED_UNKNOWN")

    def test_min_stable_three_frames_and_true_boundaries(self):
        tracker = SystemPromptWindowTracker(min_stable_frames=3)
        self.assertEqual(collect(tracker, [ui(100), ui(101)]), ())
        opened = tracker.observe(ui(102))
        self.assertEqual(opened[0].status, "PROMPT_OPENED")
        self.assertEqual(collect(tracker, [ui(103, ()), ui(104, ())]), ())
        closed = tracker.observe(ui(105, ()))
        self.assertEqual(closed[0].status, "PROMPT_DISAPPEARED_UNATTRIBUTED")

    def test_hand_boundary_resets_stale_choices_without_fabricating_pass(self):
        tracker = SystemPromptWindowTracker()
        collect(tracker, [ui(100), ui(101)])
        out = tracker.reset_for_hand_boundary()
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].status, "PROMPT_INTERRUPTED_UNKNOWN")
        self.assertEqual(out[0].to_dict()["pass_selected"], "UNKNOWN")
        new = collect(tracker, [ui(0), ui(1)])
        self.assertEqual(new[0].status, "PROMPT_OPENED")
        self.assertEqual(new[0].window_id, 2)

    def test_invalid_stability_config_fails_closed(self):
        for invalid in (1, 0, True, 2.5, -3):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    SystemPromptWindowTracker(invalid)


if __name__ == "__main__":
    unittest.main()
