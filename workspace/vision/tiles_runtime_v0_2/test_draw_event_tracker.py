from __future__ import annotations

import unittest

from .draw_event_tracker import (
    DiscardConfirmation,
    DiscardSource,
    DrawEventTracker,
    DrawState,
    VisualGeometryObservation,
)


DRAW_BOX = ((500, 400, 40, 60),)


class DrawEventTrackerTests(unittest.TestCase):
    def observation(
        self, frame: int, hand: int, draws=(), state="trusted", animation_type=None
    ) -> VisualGeometryObservation:
        return VisualGeometryObservation(
            "self", frame, hand, tuple(draws), state, animation_type, 0.9
        )

    def test_discard_other_tile_then_resort_does_not_add_draw_twice(self) -> None:
        tracker = DrawEventTracker(settle_frames=3)
        self.assertEqual(tracker.observe(self.observation(1, 10)).concealed_tile_count, 10)

        drawn = tracker.observe(self.observation(2, 10, DRAW_BOX))
        self.assertEqual(drawn.state, DrawState.DRAW_VISIBLE)
        self.assertEqual(drawn.concealed_tile_count, 11)
        self.assertIsNotNone(drawn.draw_event)

        repeated = tracker.observe(self.observation(3, 10, DRAW_BOX))
        self.assertIsNone(repeated.draw_event)
        discarded = tracker.confirm_discard(
            DiscardConfirmation("self", 4, DiscardSource.HAND, "M3", 0.95)
        )
        self.assertEqual(discarded.state, DrawState.DISCARD_CONFIRMED)
        self.assertEqual(discarded.concealed_tile_count, 10)
        self.assertIsNotNone(discarded.discard_event)

        for frame in (5, 6, 7):
            resort = tracker.observe(
                self.observation(frame, 10, state="animation", animation_type="hand_resort")
            )
            self.assertEqual(resort.state, DrawState.HAND_RESORTING)
            self.assertEqual(resort.concealed_tile_count, 10)
            self.assertFalse(resort.stable_for_hint)
            self.assertIsNone(resort.draw_event)
            self.assertIsNone(resort.discard_event)

        settled = [tracker.observe(self.observation(frame, 10)) for frame in (8, 9, 10)]
        self.assertEqual(settled[-1].state, DrawState.STABLE_HAND)
        self.assertEqual(settled[-1].concealed_tile_count, 10)
        self.assertTrue(settled[-1].stable_for_hint)
        self.assertTrue(all(output.draw_event is None for output in settled))

    def test_discard_drawn_tile_skips_hand_resort(self) -> None:
        tracker = DrawEventTracker(settle_frames=2)
        tracker.observe(self.observation(1, 10))
        tracker.observe(self.observation(2, 10, DRAW_BOX))
        discarded = tracker.confirm_discard(
            DiscardConfirmation("self", 3, DiscardSource.DRAW_VISUAL, "M8", 0.98)
        )
        self.assertEqual(discarded.state, DrawState.DISCARD_DRAWN_TILE)
        self.assertEqual(discarded.concealed_tile_count, 10)
        self.assertEqual(discarded.discard_event.source_region, DiscardSource.DRAW_VISUAL)

        first = tracker.observe(self.observation(4, 10))
        final = tracker.observe(self.observation(5, 10))
        self.assertEqual(first.state, DrawState.DISCARD_DRAWN_TILE)
        self.assertEqual(final.state, DrawState.STABLE_HAND)
        self.assertEqual(final.concealed_tile_count, 10)

    def test_resort_without_discard_fails_closed_and_emits_no_events(self) -> None:
        tracker = DrawEventTracker()
        tracker.observe(self.observation(1, 10))
        tracker.observe(self.observation(2, 10, DRAW_BOX))
        output = tracker.observe(
            self.observation(3, 10, state="animation", animation_type="hand_resort")
        )
        self.assertFalse(output.trusted)
        self.assertFalse(output.stable_for_hint)
        self.assertEqual(output.reason, "hand_resort_without_discard_confirmation")
        self.assertEqual(output.concealed_tile_count, 11)
        self.assertIsNone(output.draw_event)
        self.assertIsNone(output.discard_event)

    def test_draw_visual_cannot_silently_become_hand(self) -> None:
        tracker = DrawEventTracker()
        tracker.observe(self.observation(1, 10))
        tracker.observe(self.observation(2, 10, DRAW_BOX))
        output = tracker.observe(self.observation(3, 11))
        self.assertFalse(output.trusted)
        self.assertEqual(output.reason, "draw_visual_disappeared_without_discard_confirmation")
        self.assertEqual(output.concealed_tile_count, 11)

    def test_unknown_discard_source_does_not_change_semantic_count(self) -> None:
        tracker = DrawEventTracker()
        tracker.observe(self.observation(1, 10))
        tracker.observe(self.observation(2, 10, DRAW_BOX))
        output = tracker.confirm_discard(
            DiscardConfirmation("self", 3, DiscardSource.UNKNOWN)
        )
        self.assertFalse(output.trusted)
        self.assertEqual(output.concealed_tile_count, 11)
        self.assertEqual(output.state, DrawState.DRAW_VISIBLE)

    def test_multiple_draw_visual_components_fail_closed(self) -> None:
        tracker = DrawEventTracker()
        output = tracker.observe(
            self.observation(1, 10, ((1, 1, 2, 2), (5, 1, 2, 2)))
        )
        self.assertFalse(output.trusted)
        self.assertEqual(output.reason, "ambiguous_multiple_draw_visual_components")


if __name__ == "__main__":
    unittest.main()
