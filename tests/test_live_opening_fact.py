from __future__ import annotations

import unittest

from huian._legacy import env
from workspace.hint_alpha.runtime_pipeline import evaluate_runtime_report
from workspace.vision.current_state_snapshot import CurrentTableSnapshot
from workspace.vision.live_opening_fact import (
    LiveOpeningFactStatus,
    live_opening_fact_from_snapshot,
)


def snapshot(
    *,
    gold_tile="B",
    gold_trusted=True,
    stable_frames=3,
    input_source="runtime_vision",
    issues=(),
):
    return CurrentTableSnapshot(
        timestamp_seconds=12.5,
        source_session=(
            "manual:test" if input_source == "user_entered" else "live-session"
        ),
        stream_epoch=0,
        stable_frames=0 if input_source == "user_entered" else stable_frames,
        own_hand=(),
        gold_tile=gold_tile,
        rivers=((), ()),
        melds=((), ()),
        hand_trusted=False,
        gold_trusted=gold_trusted,
        river_trusted=(False, False),
        meld_trusted=(False, False),
        adapter_issues=tuple(issues),
        input_source=input_source,
    )


class LiveOpeningFactTests(unittest.TestCase):
    def test_trusted_runtime_gold_enters_state_tracker_boundary_only(self):
        fact = live_opening_fact_from_snapshot(snapshot())

        self.assertEqual(fact.status, LiveOpeningFactStatus.TRUSTED)
        self.assertEqual(fact.gold_tile, "B")
        self.assertTrue(fact.gold_trusted)
        self.assertTrue(fact.state_tracker_ready)
        self.assertEqual(fact.source_kind, "VISIBLE_FINAL_GOLD_MULTIFRAME")
        self.assertFalse(fact.safe_for_environment_state)
        self.assertFalse(fact.safe_for_executor)
        self.assertFalse(fact.selection_inference_used)
        self.assertEqual(fact.issues, ())

    def test_untrusted_or_single_frame_gold_remains_unknown(self):
        untrusted = live_opening_fact_from_snapshot(
            snapshot(gold_trusted=False)
        )
        self.assertEqual(untrusted.status, LiveOpeningFactStatus.UNKNOWN)
        self.assertIsNone(untrusted.gold_tile)
        self.assertFalse(untrusted.state_tracker_ready)
        self.assertIn("live_gold_untrusted", untrusted.issues)

        unstable = live_opening_fact_from_snapshot(snapshot(stable_frames=1))
        self.assertEqual(unstable.status, LiveOpeningFactStatus.UNKNOWN)
        self.assertIn("live_gold_not_multiframe_stable", unstable.issues)

    def test_final_visible_gold_cannot_be_a_flower(self):
        flower = next(iter(env.FLOWERS))
        fact = live_opening_fact_from_snapshot(snapshot(gold_tile=flower))

        self.assertEqual(fact.status, LiveOpeningFactStatus.UNKNOWN)
        self.assertIsNone(fact.gold_tile)
        self.assertIn("live_gold_flower_forbidden", fact.issues)

    def test_manual_entry_is_not_promoted_as_live_runtime_fact(self):
        fact = live_opening_fact_from_snapshot(
            snapshot(input_source="user_entered")
        )

        self.assertEqual(fact.status, LiveOpeningFactStatus.UNKNOWN)
        self.assertIn("live_opening_requires_runtime_vision", fact.issues)

    def test_runtime_gold_conflict_issue_blocks_fact_even_if_flag_is_true(self):
        fact = live_opening_fact_from_snapshot(
            snapshot(issues=("runtime_gold_identity_conflict",))
        )

        self.assertEqual(fact.status, LiveOpeningFactStatus.UNKNOWN)
        self.assertIn("runtime_gold_identity_conflict", fact.issues)

    def test_hidden_opening_metadata_cannot_populate_runtime_opening_fact(self):
        report = {
            "session": "live-session",
            "stream_epoch": 0,
            "frames": [1, 2, 3],
            "geometry_untrusted": False,
            "components": [
                {
                    "region_candidate": "gold",
                    "gold_skin": True,
                    "tile_id": "B",
                    "identity_reason": "accepted",
                    "confidence": 0.95,
                }
            ],
            "concealed_tile_count": 0,
            "all_concealed_tile_ids_trusted": False,
            "safe_for_hint": False,
            "safe_for_executor": False,
            # These fields are deliberately hostile legacy/inference inputs.
            "dice_total": 8,
            "opening_wall_index": 27,
            "random_seed": 12345,
            "inferred_gold_tile": "B",
        }

        advice = evaluate_runtime_report(report, captured=12.5, experimental=True)

        self.assertEqual(advice.opening_fact.status, LiveOpeningFactStatus.UNKNOWN)
        self.assertIsNone(advice.opening_fact.gold_tile)
        self.assertFalse(advice.opening_fact.state_tracker_ready)
        self.assertFalse(advice.opening_fact.selection_inference_used)
        self.assertIn(
            "runtime_gold_multiframe_evidence_missing",
            advice.opening_fact.issues,
        )


if __name__ == "__main__":
    unittest.main()
