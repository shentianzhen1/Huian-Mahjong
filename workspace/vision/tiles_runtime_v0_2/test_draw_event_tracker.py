from __future__ import annotations

import unittest

from .draw_event_tracker import DrawEventTracker, DrawState, VisualGeometryObservation


class DrawEventTrackerTests(unittest.TestCase):
    def observation(self, frame: int, hand: int, draws=(), state="trusted"):
        return VisualGeometryObservation("self", frame, hand, tuple(draws), state, 0.9)

    def test_draw_visual_to_hand_emits_one_event_without_double_add(self) -> None:
        tracker = DrawEventTracker(settle_frames=3)
        self.assertEqual(tracker.observe(self.observation(1, 10)).concealed_tile_count, 10)
        started = tracker.observe(self.observation(2, 10, ((500, 400, 40, 60),)))
        self.assertEqual(started.state, DrawState.DRAW_STARTED)
        self.assertEqual(started.concealed_tile_count, 11)
        visible = tracker.observe(self.observation(3, 10, ((497, 400, 40, 60),)))
        self.assertEqual(visible.state, DrawState.DRAW_VISIBLE)
        self.assertEqual(visible.concealed_tile_count, 11)
        merging = tracker.observe(self.observation(4, 10, state="animation"))
        self.assertEqual(merging.state, DrawState.DRAW_MERGING)
        self.assertFalse(merging.trusted)

        outputs = [tracker.observe(self.observation(frame, 11)) for frame in (5, 6, 7)]
        self.assertTrue(all(output.concealed_tile_count == 11 for output in outputs))
        self.assertEqual(outputs[-1].state, DrawState.DRAW_SETTLED)
        self.assertIsNotNone(outputs[-1].event)
        self.assertIsNone(outputs[-1].event.tile_id)
        self.assertEqual(outputs[-1].event.first_seen_frame, 2)
        self.assertEqual(outputs[-1].event.settled_frame, 7)

        stable = tracker.observe(self.observation(8, 11))
        self.assertEqual(stable.state, DrawState.STABLE_HAND)
        self.assertIsNone(stable.event)
        self.assertEqual(stable.concealed_tile_count, 11)

    def test_multiple_draw_visual_components_fail_closed(self) -> None:
        tracker = DrawEventTracker()
        output = tracker.observe(self.observation(1, 10, ((1, 1, 2, 2), (5, 1, 2, 2))))
        self.assertFalse(output.trusted)
        self.assertEqual(output.reason, "ambiguous_multiple_draw_visual_components")


if __name__ == "__main__":
    unittest.main()
