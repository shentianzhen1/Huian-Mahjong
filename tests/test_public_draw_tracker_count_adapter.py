"""#69 adapter tests: existing DrawEventTracker -> source-scoped stable hand count."""
from __future__ import annotations

import unittest

from workspace.vision.public_draw_tracker_count_adapter import (
    stable_draw_tracker_output_to_source_count,
)
from workspace.vision.tiles_runtime_v0_2.draw_event_tracker import (
    DrawEventTracker, VisualGeometryObservation,
)

SHA = "a" * 64


def wrap(output, **changes):
    values = dict(
        source_session="synthetic_original",
        source_sha256=SHA,
        stream_epoch=2,
        frame_index=100,
        actor="player",
        hand_geometry_region_verified=True,
        source_frame_verified=True,
        evidence_ref="stable-hand:100",
    )
    values.update(changes)
    return stable_draw_tracker_output_to_source_count(output, **values)


class DrawTrackerCountAdapterTests(unittest.TestCase):
    def test_existing_tracker_stable_hand_count_becomes_source_sample(self):
        tracker = DrawEventTracker(settle_frames=2)
        out = tracker.observe(VisualGeometryObservation(
            player="player", frame=100, hand_region_count=16,
        ))
        self.assertTrue(out.trusted)
        self.assertTrue(out.stable_for_hint)
        sample = wrap(out)
        self.assertIsNotNone(sample)
        self.assertEqual(sample.semantic_concealed_count, 16)
        self.assertEqual(sample.tracker_state, "STABLE_HAND")
        self.assertFalse(sample.draw_event_in_sample)
        self.assertFalse(sample.discard_event_in_sample)
        self.assertEqual(sample.evidence_ref, "stable-hand:100")

    def test_draw_visible_is_rejected_even_when_hint_stable(self):
        tracker = DrawEventTracker(settle_frames=2)
        tracker.observe(VisualGeometryObservation(
            player="player", frame=100, hand_region_count=16,
        ))
        out = tracker.observe(VisualGeometryObservation(
            player="player", frame=101, hand_region_count=16,
            draw_visual_bboxes=((900, 400, 40, 70),),
        ))
        self.assertTrue(out.stable_for_hint)
        self.assertIsNone(wrap(out))

    def test_untrusted_count_change_is_rejected(self):
        tracker = DrawEventTracker(settle_frames=2)
        tracker.observe(VisualGeometryObservation(
            player="player", frame=100, hand_region_count=16,
        ))
        out = tracker.observe(VisualGeometryObservation(
            player="player", frame=101, hand_region_count=15,
        ))
        self.assertFalse(out.trusted)
        self.assertIsNone(wrap(out))

    def test_source_lineage_and_verified_hand_roi_are_required(self):
        tracker = DrawEventTracker()
        out = tracker.observe(VisualGeometryObservation(
            player="player", frame=100, hand_region_count=16,
        ))
        for patch in (
            {"source_session": ""},
            {"source_sha256": "bad"},
            {"stream_epoch": True},
            {"stream_epoch": -1},
            {"frame_index": -1},
            {"actor": "system"},
            {"hand_geometry_region_verified": False},
            {"source_frame_verified": False},
            {"evidence_ref": ""},
        ):
            with self.subTest(patch=patch):
                self.assertIsNone(wrap(out, **patch))

    def test_adapter_does_not_expose_or_infer_hand_shadow(self):
        tracker = DrawEventTracker()
        out = tracker.observe(VisualGeometryObservation(
            player="player", frame=100, hand_region_count=16,
        ))
        sample = wrap(out)
        self.assertIsNotNone(sample)
        self.assertFalse(sample.draw_event_in_sample)
        self.assertFalse(sample.hand_resort_or_occlusion_in_sample)
        self.assertFalse(sample.geometry_baseline_reset_in_sample)


if __name__ == "__main__":
    unittest.main()
