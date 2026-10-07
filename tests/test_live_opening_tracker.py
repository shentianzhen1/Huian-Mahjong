from __future__ import annotations

import inspect
import unittest

from huian._legacy import env
from workspace.hint_alpha import runtime_pipeline
from workspace.hint_alpha.runtime_pipeline import RuntimeAdvicePipeline
from workspace.vision import live_opening_fact
from workspace.vision.current_state_snapshot import CurrentTableSnapshot
from workspace.vision.live_opening_fact import (
    LiveOpeningFactStatus,
    LiveOpeningTracker,
)


HAND = (
    "M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8",
    "M9", "P1", "P2", "P3", "S1", "S2", "S3", "E",
)


def snapshot(
    *,
    gold_tile="B",
    gold_trusted=True,
    session="live-session",
    epoch=0,
    stable_frames=3,
    issues=(),
):
    return CurrentTableSnapshot(
        timestamp_seconds=12.5,
        source_session=session,
        stream_epoch=epoch,
        stable_frames=stable_frames,
        own_hand=(),
        gold_tile=gold_tile,
        rivers=((), ()),
        melds=((), ()),
        hand_trusted=False,
        gold_trusted=gold_trusted,
        river_trusted=(False, False),
        meld_trusted=(False, False),
        adapter_issues=tuple(issues),
        input_source="runtime_vision",
    )


def component(region, tile, index=0):
    return {
        "region_candidate": region,
        "tile_id": tile,
        "identity_reason": "accepted",
        "normalized_bbox": [0.02 + index * 0.04, 0.80, 0.035, 0.10],
        "confidence": 0.95,
        "frame": 3,
    }


def gold_observation(frame, tile):
    return {
        "frame": frame,
        "candidate_tile_id": tile,
        "tile_id": tile,
        "tile_confidence": 0.95,
        "identity_reason": "accepted",
    }


def runtime_report(
    *,
    gold="B",
    frames=(1, 2, 3),
    session="runtime-live",
    epoch=0,
    include_gold=True,
):
    concealed = [component("hand", tile, index) for index, tile in enumerate(HAND)]
    for item in concealed:
        item["frame"] = frames[-1]
    components = list(concealed)
    payload = {
        "schema_version": "vision_runtime_v0_2_smoke",
        "session": session,
        "stream_epoch": epoch,
        "frames": list(frames),
        "components": components,
        "concealed_tile_count": len(concealed),
        "all_concealed_tile_ids_trusted": True,
        "geometry_untrusted": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }
    if include_gold:
        gold_item = component("gold", gold, len(concealed))
        gold_item["frame"] = frames[-1]
        components.append(gold_item)
        payload["gold_identity_observations"] = [
            gold_observation(frame, gold) for frame in frames
        ]
    return payload


class LiveOpeningTrackerTests(unittest.TestCase):
    def test_trusted_gold_survives_temporarily_missing_later_burst(self):
        tracker = LiveOpeningTracker()
        first, first_fact = tracker.update(snapshot(gold_tile="B"))
        missing, missing_fact = tracker.update(
            snapshot(
                gold_tile=None,
                gold_trusted=False,
                issues=(
                    "runtime_gold_component_conflict",
                    "runtime_gold_not_fully_trusted",
                ),
            )
        )

        self.assertTrue(first.gold_trusted)
        self.assertEqual(first_fact.status, LiveOpeningFactStatus.TRUSTED)
        self.assertTrue(missing.gold_trusted)
        self.assertEqual(missing.gold_tile, "B")
        self.assertEqual(missing_fact.status, LiveOpeningFactStatus.TRUSTED)
        self.assertEqual(missing_fact.source_kind, "VISIBLE_FINAL_GOLD_PERSISTED")
        self.assertIn("live_gold_carried_forward", missing.adapter_issues)
        self.assertNotIn("runtime_gold_component_conflict", missing.adapter_issues)
        self.assertFalse(missing_fact.safe_for_environment_state)
        self.assertFalse(missing_fact.safe_for_executor)
        self.assertFalse(missing_fact.selection_inference_used)

    def test_different_trusted_gold_makes_scope_sticky_unknown(self):
        tracker = LiveOpeningTracker()
        tracker.update(snapshot(gold_tile="B"))

        conflict, conflict_fact = tracker.update(snapshot(gold_tile="R"))
        recovered, recovered_fact = tracker.update(snapshot(gold_tile="B"))

        self.assertFalse(conflict.gold_trusted)
        self.assertIsNone(conflict.gold_tile)
        self.assertEqual(conflict_fact.status, LiveOpeningFactStatus.UNKNOWN)
        self.assertIn("live_gold_tracker_identity_conflict", conflict_fact.issues)
        self.assertFalse(recovered.gold_trusted)
        self.assertIsNone(recovered.gold_tile)
        self.assertIn("live_gold_tracker_conflict_sticky", recovered_fact.issues)

    def test_explicit_multiframe_identity_conflict_is_sticky_unknown(self):
        tracker = LiveOpeningTracker()
        tracker.update(snapshot(gold_tile="B"))

        conflict, fact = tracker.update(
            snapshot(
                gold_tile=None,
                gold_trusted=False,
                issues=(
                    "runtime_gold_identity_conflict",
                    "runtime_gold_not_fully_trusted",
                ),
            )
        )

        self.assertFalse(conflict.gold_trusted)
        self.assertIsNone(conflict.gold_tile)
        self.assertIn("live_gold_tracker_observation_conflict", fact.issues)

    def test_flower_gold_is_rejected_until_scope_changes(self):
        tracker = LiveOpeningTracker()
        flower = next(iter(env.FLOWERS))

        invalid, invalid_fact = tracker.update(snapshot(gold_tile=flower))
        still_invalid, still_invalid_fact = tracker.update(snapshot(gold_tile="B"))

        self.assertFalse(invalid.gold_trusted)
        self.assertIn("live_gold_flower_forbidden", invalid_fact.issues)
        self.assertFalse(still_invalid.gold_trusted)
        self.assertIn(
            "live_gold_tracker_conflict_sticky",
            still_invalid_fact.issues,
        )

    def test_new_stream_epoch_resets_conflict_and_accepts_new_gold(self):
        tracker = LiveOpeningTracker()
        tracker.update(snapshot(gold_tile="B"))
        tracker.update(snapshot(gold_tile="R"))

        reset, fact = tracker.update(snapshot(gold_tile="R", epoch=1))

        self.assertTrue(reset.gold_trusted)
        self.assertEqual(reset.gold_tile, "R")
        self.assertEqual(fact.status, LiveOpeningFactStatus.TRUSTED)

    def test_new_source_session_resets_previous_gold(self):
        tracker = LiveOpeningTracker()
        tracker.update(snapshot(gold_tile="B", session="first"))

        new_scope, fact = tracker.update(
            snapshot(gold_tile="R", session="second")
        )

        self.assertTrue(new_scope.gold_trusted)
        self.assertEqual(new_scope.gold_tile, "R")
        self.assertEqual(fact.status, LiveOpeningFactStatus.TRUSTED)

    def test_missing_initial_gold_remains_unknown(self):
        tracker = LiveOpeningTracker()
        current, fact = tracker.update(
            snapshot(
                gold_tile=None,
                gold_trusted=False,
                issues=("runtime_gold_multiframe_evidence_missing",),
            )
        )

        self.assertFalse(current.gold_trusted)
        self.assertIsNone(current.gold_tile)
        self.assertEqual(fact.status, LiveOpeningFactStatus.UNKNOWN)

    def test_runtime_pipeline_reuses_confirmed_gold_for_hint_only(self):
        pipeline = RuntimeAdvicePipeline()
        first = pipeline.evaluate(
            runtime_report(gold="B", frames=(1, 2, 3)),
            captured=1.0,
            experimental=True,
        )
        carried = pipeline.evaluate(
            runtime_report(frames=(4, 5, 6), include_gold=False),
            captured=2.0,
            experimental=True,
        )

        self.assertTrue(first.hint.allowed)
        self.assertEqual(first.snapshot.gold_tile, "B")
        self.assertTrue(carried.hint.allowed)
        self.assertEqual(carried.snapshot.gold_tile, "B")
        self.assertTrue(carried.snapshot.gold_trusted)
        self.assertEqual(
            carried.opening_fact.source_kind,
            "VISIBLE_FINAL_GOLD_PERSISTED",
        )
        self.assertFalse(carried.safe_for_executor)
        self.assertFalse(carried.opening_fact.safe_for_environment_state)

    def test_runtime_pipeline_blocks_hint_after_different_stable_gold(self):
        pipeline = RuntimeAdvicePipeline()
        first = pipeline.evaluate(
            runtime_report(gold="B", frames=(1, 2, 3)),
            captured=1.0,
            experimental=True,
        )
        conflict = pipeline.evaluate(
            runtime_report(gold="R", frames=(4, 5, 6)),
            captured=2.0,
            experimental=True,
        )

        self.assertTrue(first.hint.allowed)
        self.assertFalse(conflict.hint.allowed)
        self.assertFalse(conflict.display_allowed)
        self.assertIsNone(conflict.snapshot.gold_tile)
        self.assertIn("gold_untrusted", conflict.hint.issues)

    def test_live_pipeline_has_no_simulator_dice_or_wall_dependency(self):
        source = inspect.getsource(live_opening_fact) + inspect.getsource(runtime_pipeline)

        self.assertNotIn("workspace.simulator", source)
        self.assertNotIn("dice_total", source)
        self.assertNotIn("wall_index", source)
        self.assertNotIn("random_seed", source)


if __name__ == "__main__":
    unittest.main()
