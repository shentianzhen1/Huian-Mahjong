from __future__ import annotations

import unittest

from workspace.vision.public_match_reconstruction import ObservationKind
from workspace.vision.public_observers import MeldSnapshotObserver
from workspace.vision.runtime_public_adapter import (
    player_hand_delta_from_runtime,
    player_meld_snapshot_from_runtime,
)


def component(
    x: float,
    region: str,
    *,
    tile_id: str = "UNKNOWN",
    confidence: float = 0.95,
    frame: int = 100,
    y: float = 0.80,
    width: float = 0.04,
    height: float = 0.10,
) -> dict:
    return {
        "normalized_bbox": [x, y, width, height],
        "region_candidate": region,
        "confidence": confidence,
        "frame": frame,
        "tile_id": tile_id,
        "tile_confidence": confidence,
    }


def report(
    components: list[dict],
    *,
    concealed_count: int | None = None,
    all_ids_trusted: bool = False,
    geometry_untrusted: bool = False,
    frame: int = 100,
    session: str = "session_test",
) -> dict:
    if concealed_count is None:
        concealed_count = sum(
            item["region_candidate"] in {"hand", "draw_visual"}
            for item in components
        )
    return {
        "schema_version": "vision_runtime_v0_2_smoke",
        "session": session,
        "frames": [frame - 2, frame - 1, frame],
        "components": components,
        "concealed_tile_count": concealed_count,
        "all_concealed_tile_ids_trusted": all_ids_trusted,
        "geometry_untrusted": geometry_untrusted,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


class RuntimePublicAdapterMeldTests(unittest.TestCase):
    def test_runtime_meld_components_become_player_meld_snapshot(self):
        source = report(
            [
                component(0.05, "meld", frame=100),
                component(0.09, "meld", frame=100),
                component(0.13, "meld", frame=100),
                component(0.45, "hand", tile_id="M1", frame=100),
            ],
            frame=100,
        )
        snapshot = player_meld_snapshot_from_runtime(
            source,
            timestamp_seconds=12.5,
        )
        self.assertTrue(snapshot.trusted)
        self.assertEqual(snapshot.actor, "player")
        self.assertEqual(len(snapshot.groups), 1)
        group = snapshot.groups[0]
        self.assertEqual(group.tiles, (None, None, None))
        self.assertFalse(group.identities_complete)
        self.assertIn("runtime:session_test:frame:100", group.evidence_refs)

    def test_future_trusted_meld_identity_is_preserved_without_new_classifier_logic(self):
        source = report(
            [
                component(0.05, "meld", tile_id="P3"),
                component(0.09, "meld", tile_id="P4"),
                component(0.13, "meld", tile_id="P5"),
            ]
        )
        snapshot = player_meld_snapshot_from_runtime(source, timestamp_seconds=2.0)
        self.assertEqual(snapshot.groups[0].tiles, ("P3", "P4", "P5"))
        self.assertTrue(snapshot.groups[0].identities_complete)

    def test_distant_meld_components_form_separate_groups(self):
        source = report(
            [
                component(0.05, "meld"),
                component(0.09, "meld"),
                component(0.13, "meld"),
                component(0.30, "meld"),
                component(0.34, "meld"),
                component(0.38, "meld"),
            ]
        )
        snapshot = player_meld_snapshot_from_runtime(source, timestamp_seconds=2.0)
        self.assertEqual(len(snapshot.groups), 2)
        self.assertTrue(all(len(group.tiles) == 3 for group in snapshot.groups))

    def test_stacked_four_face_group_stays_one_group(self):
        source = report(
            [
                component(0.10, "meld", y=0.78),
                component(0.14, "meld", y=0.78),
                component(0.14, "meld", y=0.82),
                component(0.18, "meld", y=0.82),
            ]
        )
        snapshot = player_meld_snapshot_from_runtime(source, timestamp_seconds=2.0)
        self.assertEqual(len(snapshot.groups), 1)
        self.assertEqual(len(snapshot.groups[0].tiles), 4)

    def test_geometry_untrusted_report_produces_untrusted_empty_snapshot(self):
        source = report(
            [
                component(0.05, "meld"),
                component(0.09, "meld"),
                component(0.13, "meld"),
            ],
            geometry_untrusted=True,
        )
        snapshot = player_meld_snapshot_from_runtime(source, timestamp_seconds=2.0)
        self.assertFalse(snapshot.trusted)
        self.assertEqual(snapshot.groups, ())

    def test_runtime_meld_snapshot_flows_into_stability_observer(self):
        observer = MeldSnapshotObserver(settle_frames=2)
        empty = report([], frame=100)
        for i in range(2):
            observer.observe(
                player_meld_snapshot_from_runtime(
                    {**empty, "frames": [98 + i, 99 + i, 100 + i]},
                    timestamp_seconds=1.0 + i * 0.1,
                )
            )

        source = report(
            [
                component(0.05, "meld", frame=120),
                component(0.09, "meld", frame=120),
                component(0.13, "meld", frame=120),
            ],
            frame=120,
        )
        output = None
        for i in range(2):
            current = {
                **source,
                "frames": [118 + i, 119 + i, 120 + i],
                "components": [
                    {**item, "frame": 120 + i}
                    for item in source["components"]
                ],
            }
            output = observer.observe(
                player_meld_snapshot_from_runtime(
                    current,
                    timestamp_seconds=2.0 + i * 0.1,
                )
            )

        assert output is not None
        self.assertTrue(output.stable)
        self.assertIsNotNone(output.observation)
        observation = output.observation
        assert observation is not None
        self.assertEqual(observation.kind, ObservationKind.MELD_DELTA)
        self.assertEqual(observation.tiles, ())
        self.assertFalse(observation.details["tile_identity_complete"])


class RuntimePublicAdapterHandDeltaTests(unittest.TestCase):
    def test_count_only_hand_delta_when_identity_not_trusted(self):
        before = report(
            [
                component(0.40, "hand", tile_id="M1"),
                component(0.44, "hand", tile_id="M2"),
                component(0.48, "hand", tile_id="M3"),
                component(0.52, "hand", tile_id="M4"),
            ],
            concealed_count=4,
            all_ids_trusted=False,
            frame=100,
        )
        after = report(
            [
                component(0.40, "hand", tile_id="M1", frame=110),
                component(0.44, "hand", tile_id="M4", frame=110),
            ],
            concealed_count=2,
            all_ids_trusted=False,
            frame=110,
        )
        delta = player_hand_delta_from_runtime(
            before,
            after,
            timestamp_seconds=5.0,
        )
        assert delta is not None
        self.assertEqual(delta.kind, ObservationKind.HAND_DELTA)
        self.assertEqual(delta.details["removed_count"], 2)
        self.assertEqual(delta.details["added_count"], 0)
        self.assertFalse(delta.details["identity_delta_observed"])
        self.assertNotIn("removed_tiles", delta.details)

    def test_exact_multiset_delta_when_both_reports_trust_all_identities(self):
        before = report(
            [
                component(0.40, "hand", tile_id="P3"),
                component(0.44, "hand", tile_id="P4"),
                component(0.48, "hand", tile_id="S1"),
                component(0.52, "draw_visual", tile_id="E"),
            ],
            concealed_count=4,
            all_ids_trusted=True,
            frame=100,
        )
        after = report(
            [
                component(0.40, "hand", tile_id="S1", frame=110),
                component(0.44, "hand", tile_id="E", frame=110),
            ],
            concealed_count=2,
            all_ids_trusted=True,
            frame=110,
        )
        delta = player_hand_delta_from_runtime(
            before,
            after,
            timestamp_seconds=5.0,
        )
        assert delta is not None
        self.assertEqual(delta.details["removed_count"], 2)
        self.assertEqual(delta.details["removed_tiles"], ["P3", "P4"])
        self.assertEqual(delta.details["added_tiles"], [])
        self.assertTrue(delta.details["identity_delta_observed"])

    def test_added_tile_delta_is_observed_without_semantic_draw_inference(self):
        before = report(
            [component(0.40, "hand", tile_id="M1")],
            concealed_count=1,
            all_ids_trusted=True,
            frame=100,
        )
        after = report(
            [
                component(0.40, "hand", tile_id="M1", frame=110),
                component(0.50, "draw_visual", tile_id="P9", frame=110),
            ],
            concealed_count=2,
            all_ids_trusted=True,
            frame=110,
        )
        delta = player_hand_delta_from_runtime(before, after, timestamp_seconds=5.0)
        assert delta is not None
        self.assertEqual(delta.details["removed_count"], 0)
        self.assertEqual(delta.details["added_count"], 1)
        self.assertEqual(delta.details["added_tiles"], ["P9"])
        self.assertEqual(delta.kind, ObservationKind.HAND_DELTA)

    def test_equal_concealed_count_has_no_count_delta_event(self):
        before = report(
            [component(0.40, "hand", tile_id="M1")],
            concealed_count=1,
            all_ids_trusted=True,
        )
        after = report(
            [component(0.40, "hand", tile_id="M2")],
            concealed_count=1,
            all_ids_trusted=True,
        )
        self.assertIsNone(
            player_hand_delta_from_runtime(
                before,
                after,
                timestamp_seconds=5.0,
            )
        )

    def test_untrusted_geometry_does_not_emit_hand_delta(self):
        before = report([], concealed_count=4, geometry_untrusted=True)
        after = report([], concealed_count=2)
        self.assertIsNone(
            player_hand_delta_from_runtime(
                before,
                after,
                timestamp_seconds=5.0,
            )
        )


if __name__ == "__main__":
    unittest.main()
