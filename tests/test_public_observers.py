from __future__ import annotations

import unittest

from workspace.vision.public_match_reconstruction import (
    ObservationKind,
    PublicActionKind,
    RawObservation,
    reconstruct_claimed_meld,
)
from workspace.vision.public_observers import (
    DiscardRiverObserver,
    MeldGroup,
    MeldSnapshot,
    MeldSnapshotObserver,
    PublicTile,
    RiverSnapshot,
)


def tile(x: float, tile_id: str | None, *, confidence: float = 0.99, ref: str = "") -> PublicTile:
    return PublicTile(
        normalized_bbox=(x, 0.40, 0.04, 0.08),
        tile_id=tile_id,
        confidence=confidence,
        evidence_refs=((ref,) if ref else ()),
    )


def river(
    t: float,
    actor: str,
    tiles: tuple[PublicTile, ...],
    *,
    frame: int,
    trusted: bool = True,
    stream_epoch: int = 0,
) -> RiverSnapshot:
    return RiverSnapshot(
        timestamp_seconds=t,
        actor=actor,
        tiles=tiles,
        frame=frame,
        trusted=trusted,
        evidence_refs=(f"frame:{frame}",),
        stream_epoch=stream_epoch,
    )


def meld(
    x: float,
    tiles: tuple[str | None, ...],
    *,
    confidence: float = 0.98,
    ref: str = "",
) -> MeldGroup:
    return MeldGroup(
        normalized_bbox=(x, 0.76, 0.13 if len(tiles) == 3 else 0.16, 0.12),
        tiles=tiles,
        confidence=confidence,
        evidence_refs=((ref,) if ref else ()),
    )


def meld_frame(
    t: float,
    actor: str,
    groups: tuple[MeldGroup, ...],
    *,
    frame: int,
    trusted: bool = True,
    stream_epoch: int = 0,
) -> MeldSnapshot:
    return MeldSnapshot(
        timestamp_seconds=t,
        actor=actor,
        groups=groups,
        frame=frame,
        trusted=trusted,
        evidence_refs=(f"frame:{frame}",),
        stream_epoch=stream_epoch,
    )


class DiscardRiverObserverTests(unittest.TestCase):
    def _settle(self, observer: DiscardRiverObserver, snapshot_factory):
        outputs = []
        for index in range(observer.settle_frames):
            outputs.append(observer.observe(snapshot_factory(index)))
        return outputs[-1]

    def test_establishes_baseline_without_fake_discard(self):
        observer = DiscardRiverObserver(settle_frames=3)
        output = self._settle(
            observer,
            lambda i: river(
                1 + i * 0.1,
                "opponent",
                (tile(0.20, "M3"), tile(0.25, "P4")),
                frame=10 + i,
            ),
        )
        self.assertTrue(output.stable)
        self.assertIsNone(output.observation)
        self.assertEqual(output.issues, ("river_baseline_established",))

    def test_one_stable_new_tile_emits_discard(self):
        observer = DiscardRiverObserver(settle_frames=2)
        self._settle(
            observer,
            lambda i: river(
                1 + i * 0.1,
                "opponent",
                (tile(0.20, "M3"),),
                frame=10 + i,
            ),
        )
        output = self._settle(
            observer,
            lambda i: river(
                2 + i * 0.1,
                "opponent",
                (
                    tile(0.201, "M3"),
                    tile(0.26, "P5", confidence=0.97, ref="discard:P5"),
                ),
                frame=20 + i,
            ),
        )
        self.assertTrue(output.stable)
        self.assertTrue(output.trusted)
        self.assertIsNotNone(output.observation)
        observation = output.observation
        assert observation is not None
        self.assertEqual(observation.kind, ObservationKind.DISCARD)
        self.assertEqual(observation.actor, "opponent")
        self.assertEqual(observation.tile, "P5")
        self.assertEqual(observation.confidence, 0.97)
        self.assertEqual(observation.details["previous_river_count"], 1)
        self.assertEqual(observation.details["current_river_count"], 2)

    def test_unknown_tile_identity_emits_unknown_friendly_discard_fact(self):
        observer = DiscardRiverObserver(settle_frames=2)
        self._settle(
            observer,
            lambda i: river(1 + i * 0.1, "player", (), frame=10 + i),
        )
        output = self._settle(
            observer,
            lambda i: river(
                2 + i * 0.1,
                "player",
                (tile(0.30, None, confidence=0.70),),
                frame=20 + i,
            ),
        )
        observation = output.observation
        assert observation is not None
        self.assertIsNone(observation.tile)
        self.assertFalse(observation.details["tile_identity_observed"])

    def test_single_frame_transient_does_not_emit(self):
        observer = DiscardRiverObserver(settle_frames=3)
        self._settle(
            observer,
            lambda i: river(1 + i * 0.1, "player", (tile(0.20, "M1"),), frame=10 + i),
        )
        transient = observer.observe(
            river(2.0, "player", (tile(0.20, "M1"), tile(0.25, "M2")), frame=20)
        )
        back = observer.observe(
            river(2.1, "player", (tile(0.20, "M1"),), frame=21)
        )
        self.assertFalse(transient.stable)
        self.assertFalse(back.stable)
        self.assertIsNone(transient.observation)
        self.assertIsNone(back.observation)

    def test_small_geometry_jitter_does_not_create_new_tile(self):
        observer = DiscardRiverObserver(settle_frames=2)
        self._settle(
            observer,
            lambda i: river(
                1 + i * 0.1,
                "player",
                (tile(0.20, "M1"), tile(0.25, "M2")),
                frame=10 + i,
            ),
        )
        output = self._settle(
            observer,
            lambda i: river(
                2 + i * 0.1,
                "player",
                (tile(0.202, "M1"), tile(0.248, "M2")),
                frame=20 + i,
            ),
        )
        self.assertTrue(output.stable)
        self.assertTrue(output.trusted)
        self.assertIsNone(output.observation)

    def test_claimed_or_removed_river_tile_is_not_fake_discard(self):
        observer = DiscardRiverObserver(settle_frames=2)
        self._settle(
            observer,
            lambda i: river(
                1 + i * 0.1,
                "opponent",
                (tile(0.20, "M1"), tile(0.25, "P5")),
                frame=10 + i,
            ),
        )
        output = self._settle(
            observer,
            lambda i: river(
                2 + i * 0.1,
                "opponent",
                (tile(0.20, "M1"),),
                frame=20 + i,
            ),
        )
        self.assertIsNone(output.observation)
        self.assertTrue(output.baseline_rebased)
        self.assertIn("river_tile_removed_or_claimed", output.issues)

    def test_two_new_tiles_after_missed_frames_are_ambiguous_not_two_guesses(self):
        observer = DiscardRiverObserver(settle_frames=2)
        self._settle(
            observer,
            lambda i: river(1 + i * 0.1, "opponent", (), frame=10 + i),
        )
        output = self._settle(
            observer,
            lambda i: river(
                3 + i * 0.1,
                "opponent",
                (tile(0.20, "M1"), tile(0.25, "M2")),
                frame=30 + i,
            ),
        )
        self.assertIsNone(output.observation)
        self.assertFalse(output.trusted)
        self.assertTrue(output.baseline_rebased)
        self.assertEqual(output.issues, ("river_transition_ambiguous",))

    def test_stream_epoch_change_reestablishes_river_baseline(self):
        observer = DiscardRiverObserver(settle_frames=2)
        self._settle(
            observer,
            lambda i: river(
                1 + i * 0.1,
                "opponent",
                (tile(0.20, "M1"),),
                frame=10 + i,
                stream_epoch=0,
            ),
        )

        first_new_epoch = observer.observe(
            river(
                5.0,
                "opponent",
                (tile(0.20, "M1"), tile(0.25, "M2")),
                frame=50,
                stream_epoch=1,
            )
        )
        self.assertFalse(first_new_epoch.stable)
        self.assertTrue(first_new_epoch.baseline_rebased)
        self.assertEqual(
            first_new_epoch.issues,
            ("river_stream_epoch_reset",),
        )

        new_baseline = observer.observe(
            river(
                5.1,
                "opponent",
                (tile(0.20, "M1"), tile(0.25, "M2")),
                frame=51,
                stream_epoch=1,
            )
        )
        self.assertTrue(new_baseline.stable)
        self.assertIsNone(new_baseline.observation)
        self.assertEqual(
            new_baseline.issues,
            ("river_baseline_established",),
        )

        first_plus_one = observer.observe(
            river(
                6.0,
                "opponent",
                (
                    tile(0.20, "M1"),
                    tile(0.25, "M2"),
                    tile(0.30, "M3"),
                ),
                frame=60,
                stream_epoch=1,
            )
        )
        self.assertFalse(first_plus_one.stable)
        discard = observer.observe(
            river(
                6.1,
                "opponent",
                (
                    tile(0.20, "M1"),
                    tile(0.25, "M2"),
                    tile(0.30, "M3"),
                ),
                frame=61,
                stream_epoch=1,
            )
        )
        self.assertIsNotNone(discard.observation)
        self.assertEqual(discard.observation.tile, "M3")

    def test_untrusted_snapshot_does_not_change_baseline(self):
        observer = DiscardRiverObserver(settle_frames=2)
        self._settle(
            observer,
            lambda i: river(1 + i * 0.1, "player", (), frame=10 + i),
        )
        bad = observer.observe(
            river(1.5, "player", (tile(0.20, "M9"),), frame=15, trusted=False)
        )
        self.assertFalse(bad.trusted)
        output = self._settle(
            observer,
            lambda i: river(
                2 + i * 0.1,
                "player",
                (tile(0.25, "P2"),),
                frame=20 + i,
            ),
        )
        self.assertEqual(output.observation.tile, "P2")


class MeldSnapshotObserverTests(unittest.TestCase):
    def _settle(self, observer: MeldSnapshotObserver, snapshot_factory):
        outputs = []
        for index in range(observer.settle_frames):
            outputs.append(observer.observe(snapshot_factory(index)))
        return outputs[-1]

    def test_establishes_meld_baseline_without_event(self):
        observer = MeldSnapshotObserver(settle_frames=2)
        output = self._settle(
            observer,
            lambda i: meld_frame(
                1 + i * 0.1,
                "player",
                (meld(0.05, ("E", "E", "E")),),
                frame=10 + i,
            ),
        )
        self.assertTrue(output.stable)
        self.assertIsNone(output.observation)
        self.assertEqual(output.issues, ("meld_baseline_established",))

    def test_new_exposed_group_emits_meld_delta(self):
        observer = MeldSnapshotObserver(settle_frames=2)
        self._settle(
            observer,
            lambda i: meld_frame(
                1 + i * 0.1,
                "player",
                (meld(0.05, ("E", "E", "E")),),
                frame=10 + i,
            ),
        )
        output = self._settle(
            observer,
            lambda i: meld_frame(
                2 + i * 0.1,
                "player",
                (
                    meld(0.051, ("E", "E", "E")),
                    meld(0.22, ("P3", "P4", "P5"), ref="meld:P345"),
                ),
                frame=20 + i,
            ),
        )
        observation = output.observation
        assert observation is not None
        self.assertEqual(observation.kind, ObservationKind.MELD_DELTA)
        self.assertEqual(observation.tiles, ("P3", "P4", "P5"))
        self.assertTrue(observation.details["tile_identity_complete"])
        self.assertEqual(observation.details["group_size"], 3)

    def test_group_order_change_does_not_emit(self):
        observer = MeldSnapshotObserver(settle_frames=2)
        left = meld(0.05, ("E", "E", "E"))
        right = meld(0.25, ("P3", "P4", "P5"))
        self._settle(
            observer,
            lambda i: meld_frame(1 + i * 0.1, "player", (left, right), frame=10 + i),
        )
        output = self._settle(
            observer,
            lambda i: meld_frame(
                2 + i * 0.1,
                "player",
                (
                    meld(0.251, ("P5", "P3", "P4")),
                    meld(0.051, ("E", "E", "E")),
                ),
                frame=20 + i,
            ),
        )
        self.assertTrue(output.stable)
        self.assertIsNone(output.observation)

    def test_three_to_four_group_emits_previous_meld_for_add_kong_reconstruction(self):
        observer = MeldSnapshotObserver(settle_frames=2)
        self._settle(
            observer,
            lambda i: meld_frame(
                1 + i * 0.1,
                "opponent",
                (meld(0.10, ("S8", "S8", "S8")),),
                frame=10 + i,
            ),
        )
        output = self._settle(
            observer,
            lambda i: meld_frame(
                2 + i * 0.1,
                "opponent",
                (meld(0.101, ("S8", "S8", "S8", "S8")),),
                frame=20 + i,
            ),
        )
        observation = output.observation
        assert observation is not None
        self.assertEqual(observation.tiles, ("S8", "S8", "S8", "S8"))
        self.assertEqual(
            observation.details["previous_meld"],
            ["S8", "S8", "S8"],
        )
        self.assertEqual(observation.details["previous_group_size"], 3)

    def test_incomplete_meld_identity_emits_unknown_friendly_delta(self):
        observer = MeldSnapshotObserver(settle_frames=2)
        self._settle(
            observer,
            lambda i: meld_frame(1 + i * 0.1, "player", (), frame=10 + i),
        )
        output = self._settle(
            observer,
            lambda i: meld_frame(
                2 + i * 0.1,
                "player",
                (meld(0.10, ("M3", None, "M5")),),
                frame=20 + i,
            ),
        )
        observation = output.observation
        assert observation is not None
        self.assertEqual(observation.tiles, ())
        self.assertFalse(observation.details["tile_identity_complete"])
        self.assertIn("meld_identity_incomplete", output.issues)

    def test_multiple_new_groups_are_ambiguous_and_rebased(self):
        observer = MeldSnapshotObserver(settle_frames=2)
        self._settle(
            observer,
            lambda i: meld_frame(1 + i * 0.1, "player", (), frame=10 + i),
        )
        output = self._settle(
            observer,
            lambda i: meld_frame(
                3 + i * 0.1,
                "player",
                (
                    meld(0.10, ("M1", "M2", "M3")),
                    meld(0.30, ("P7", "P7", "P7")),
                ),
                frame=30 + i,
            ),
        )
        self.assertIsNone(output.observation)
        self.assertFalse(output.trusted)
        self.assertTrue(output.baseline_rebased)
        self.assertEqual(output.issues, ("meld_transition_ambiguous",))

    def test_stream_epoch_change_reestablishes_meld_baseline(self):
        observer = MeldSnapshotObserver(settle_frames=2)
        self._settle(
            observer,
            lambda i: meld_frame(
                1 + i * 0.1,
                "player",
                (meld(0.05, ("E", "E", "E")),),
                frame=10 + i,
                stream_epoch=0,
            ),
        )

        first_new_epoch = observer.observe(
            meld_frame(
                5.0,
                "player",
                (
                    meld(0.05, ("E", "E", "E")),
                    meld(0.25, ("P3", "P4", "P5")),
                ),
                frame=50,
                stream_epoch=1,
            )
        )
        self.assertFalse(first_new_epoch.stable)
        self.assertTrue(first_new_epoch.baseline_rebased)
        self.assertEqual(
            first_new_epoch.issues,
            ("meld_stream_epoch_reset",),
        )

        new_baseline = observer.observe(
            meld_frame(
                5.1,
                "player",
                (
                    meld(0.05, ("E", "E", "E")),
                    meld(0.25, ("P3", "P4", "P5")),
                ),
                frame=51,
                stream_epoch=1,
            )
        )
        self.assertTrue(new_baseline.stable)
        self.assertIsNone(new_baseline.observation)
        self.assertEqual(
            new_baseline.issues,
            ("meld_baseline_established",),
        )

    def test_one_frame_meld_animation_does_not_emit(self):
        observer = MeldSnapshotObserver(settle_frames=3)
        self._settle(
            observer,
            lambda i: meld_frame(1 + i * 0.1, "opponent", (), frame=10 + i),
        )
        first = observer.observe(
            meld_frame(
                2.0,
                "opponent",
                (meld(0.20, ("R", "R", "R")),),
                frame=20,
            )
        )
        second = observer.observe(meld_frame(2.1, "opponent", (), frame=21))
        self.assertFalse(first.stable)
        self.assertFalse(second.stable)
        self.assertIsNone(first.observation)
        self.assertIsNone(second.observation)



class PublicObserverPipelineIntegrationTests(unittest.TestCase):
    def test_player_discard_to_opponent_chi_end_to_end(self):
        river_observer = DiscardRiverObserver(settle_frames=2)
        meld_observer = MeldSnapshotObserver(settle_frames=2)

        # Establish empty public baselines.
        for i in range(2):
            river_observer.observe(
                river(1 + i * 0.1, "player", (), frame=10 + i)
            )
            meld_observer.observe(
                meld_frame(1 + i * 0.1, "opponent", (), frame=10 + i)
            )

        discard_output = None
        for i in range(2):
            discard_output = river_observer.observe(
                river(
                    2 + i * 0.1,
                    "player",
                    (tile(0.30, "S6", ref="river:S6"),),
                    frame=20 + i,
                )
            )
        assert discard_output is not None
        discard = discard_output.observation
        assert discard is not None

        meld_output = None
        for i in range(2):
            meld_output = meld_observer.observe(
                meld_frame(
                    2.3 + i * 0.1,
                    "opponent",
                    (meld(0.15, ("S4", "S5", "S6"), ref="meld:S456"),),
                    frame=23 + i,
                )
            )
        assert meld_output is not None
        meld_delta = meld_output.observation
        assert meld_delta is not None

        opponent_hand_delta = RawObservation(
            timestamp_seconds=2.25,
            actor="opponent",
            kind=ObservationKind.HAND_DELTA,
            confidence=0.96,
            evidence_refs=("opponent_count:2_removed",),
            details={"removed_count": 2},
        )

        action = reconstruct_claimed_meld(
            discard,
            opponent_hand_delta,
            meld_delta,
        )
        self.assertEqual(action.kind, PublicActionKind.CHI)
        self.assertEqual(action.claimed_tile, "S6")
        self.assertEqual(action.meld, ("S4", "S5", "S6"))
        self.assertEqual(action.consumed_from_hand, ("S4", "S5"))
        self.assertFalse(action.details["hand_delta_identity_observed"])
        self.assertEqual(
            set(action.evidence_refs),
            {
                "frame:11",
                "frame:21",
                "river:S6",
                "frame:24",
                "meld:S456",
                "opponent_count:2_removed",
            },
        )


if __name__ == "__main__":
    unittest.main()
