from __future__ import annotations

import unittest

from workspace.vision.action_assembler import AssemblyConfig, TemporalActionAssembler
from workspace.vision.public_match_reconstruction import (
    EvidenceGrade,
    ObservationKind,
    PublicActionKind,
    RawObservation,
)


def obs(
    t: float,
    actor: str,
    kind: ObservationKind,
    *,
    tile: str | None = None,
    tiles: tuple[str, ...] = (),
    confidence: float = 0.99,
    refs: tuple[str, ...] = (),
    details: dict | None = None,
) -> RawObservation:
    return RawObservation(
        timestamp_seconds=t,
        actor=actor,
        kind=kind,
        tile=tile,
        tiles=tiles,
        confidence=confidence,
        evidence_refs=refs,
        details=details or {},
    )


class TemporalActionAssemblerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = AssemblyConfig(
            claim_window_seconds=3.0,
            assembly_delay_seconds=0.4,
        )

    def test_config_is_explicit_and_validated(self):
        with self.assertRaises(ValueError):
            AssemblyConfig(0.0, 0.0)
        with self.assertRaises(ValueError):
            AssemblyConfig(1.0, 1.1)

    def test_direct_discard_is_emitted_immediately_but_retained_for_claim(self):
        assembler = TemporalActionAssembler(self.config)
        actions = assembler.ingest(
            obs(
                1.0,
                "opponent",
                ObservationKind.DISCARD,
                tile="P5",
                refs=("river:P5",),
            )
        )
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].kind, PublicActionKind.DISCARD)
        self.assertEqual(actions[0].tile, "P5")
        self.assertEqual(actions[0].evidence_grade, EvidenceGrade.DIRECT)

        assembler.ingest(
            obs(
                1.2,
                "player",
                ObservationKind.MELD_DELTA,
                tiles=("P3", "P4", "P5"),
                refs=("meld:P345",),
            )
        )
        assembler.ingest(
            obs(
                1.3,
                "player",
                ObservationKind.HAND_DELTA,
                refs=("hand:minus:P3P4",),
                details={"removed_tiles": ["P3", "P4"]},
            )
        )
        actions = assembler.advance_time(1.7)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].kind, PublicActionKind.CHI)
        self.assertEqual(actions[0].claimed_tile, "P5")
        self.assertEqual(actions[0].consumed_from_hand, ("P3", "P4"))
        self.assertEqual(
            set(actions[0].evidence_refs),
            {"river:P5", "meld:P345", "hand:minus:P3P4"},
        )

    def test_delay_prevents_premature_unknown_before_hand_delta_arrives(self):
        assembler = TemporalActionAssembler(self.config)
        assembler.ingest(
            obs(1.0, "opponent", ObservationKind.DISCARD, tile="E")
        )
        self.assertEqual(
            assembler.ingest(
                obs(
                    1.2,
                    "player",
                    ObservationKind.MELD_DELTA,
                    tiles=("E", "E", "E"),
                )
            ),
            (),
        )
        self.assertEqual(
            assembler.ingest(
                obs(
                    1.3,
                    "player",
                    ObservationKind.HAND_DELTA,
                    details={"removed_tiles": ["E", "E"]},
                )
            ),
            (),
        )
        actions = assembler.advance_time(1.6)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].kind, PublicActionKind.PENG)

    def test_opponent_claim_uses_count_only_hand_delta(self):
        assembler = TemporalActionAssembler(self.config)
        assembler.ingest(
            obs(10.0, "player", ObservationKind.DISCARD, tile="S6")
        )
        assembler.ingest(
            obs(
                10.2,
                "opponent",
                ObservationKind.MELD_DELTA,
                tiles=("S4", "S5", "S6"),
            )
        )
        assembler.ingest(
            obs(
                10.3,
                "opponent",
                ObservationKind.HAND_DELTA,
                details={"removed_count": 2},
            )
        )
        actions = assembler.advance_time(10.7)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].kind, PublicActionKind.CHI)
        self.assertFalse(actions[0].details["hand_delta_identity_observed"])

    def test_ming_gang_assembles_from_discard_and_three_removed(self):
        assembler = TemporalActionAssembler(self.config)
        assembler.ingest(
            obs(3.0, "opponent", ObservationKind.DISCARD, tile="M7")
        )
        assembler.ingest(
            obs(
                3.1,
                "player",
                ObservationKind.HAND_DELTA,
                details={"removed_tiles": ["M7", "M7", "M7"]},
            )
        )
        assembler.ingest(
            obs(
                3.2,
                "player",
                ObservationKind.MELD_DELTA,
                tiles=("M7", "M7", "M7", "M7"),
            )
        )
        actions = assembler.advance_time(3.7)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].kind, PublicActionKind.MING_GANG)

    def test_add_kong_uses_previous_peng_and_does_not_require_discard(self):
        assembler = TemporalActionAssembler(self.config)
        assembler.ingest(
            obs(
                5.0,
                "player",
                ObservationKind.HAND_DELTA,
                details={"removed_tiles": ["P1"]},
                refs=("hand:P1",),
            )
        )
        assembler.ingest(
            obs(
                5.1,
                "player",
                ObservationKind.MELD_DELTA,
                tiles=("P1", "P1", "P1", "P1"),
                refs=("meld:P1111",),
                details={"previous_meld": ["P1", "P1", "P1"]},
            )
        )
        actions = assembler.advance_time(5.6)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].kind, PublicActionKind.ADD_KONG)
        self.assertEqual(actions[0].tile, "P1")

    def test_latest_unrelated_discard_does_not_force_meld_classification(self):
        assembler = TemporalActionAssembler(self.config)
        assembler.ingest(
            obs(1.0, "opponent", ObservationKind.DISCARD, tile="P9")
        )
        assembler.ingest(
            obs(
                1.2,
                "player",
                ObservationKind.HAND_DELTA,
                details={"removed_tiles": ["P3", "P4"]},
            )
        )
        assembler.ingest(
            obs(
                1.3,
                "player",
                ObservationKind.MELD_DELTA,
                tiles=("P3", "P4", "P5"),
            )
        )
        self.assertEqual(assembler.advance_time(1.8), ())
        actions = assembler.advance_time(4.31)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].kind, PublicActionKind.UNKNOWN_ACTION)
        self.assertEqual(
            actions[0].unknown_reasons,
            ("meld_window_expired_without_unique_reconstruction",),
        )

    def test_incomplete_meld_identity_expires_unknown_instead_of_guessing(self):
        assembler = TemporalActionAssembler(self.config)
        assembler.ingest(
            obs(1.0, "opponent", ObservationKind.DISCARD, tile="P5")
        )
        assembler.ingest(
            obs(
                1.2,
                "player",
                ObservationKind.MELD_DELTA,
                tiles=(),
                details={
                    "group_size": 3,
                    "tile_identity_complete": False,
                    "tile_candidates": ["P3", None, "P5"],
                },
            )
        )
        assembler.ingest(
            obs(
                1.3,
                "player",
                ObservationKind.HAND_DELTA,
                details={"removed_count": 2},
            )
        )
        actions = assembler.advance_time(4.21)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].kind, PublicActionKind.UNKNOWN_ACTION)
        self.assertEqual(actions[0].evidence_grade, EvidenceGrade.UNKNOWN)

    def test_multiple_valid_hand_delta_combinations_fail_closed(self):
        assembler = TemporalActionAssembler(self.config)
        assembler.ingest(
            obs(1.0, "opponent", ObservationKind.DISCARD, tile="E")
        )
        assembler.ingest(
            obs(
                1.10,
                "player",
                ObservationKind.HAND_DELTA,
                details={"removed_tiles": ["E", "E"]},
                refs=("hand:a",),
            )
        )
        assembler.ingest(
            obs(
                1.15,
                "player",
                ObservationKind.HAND_DELTA,
                details={"removed_tiles": ["E", "E"]},
                refs=("hand:b",),
            )
        )
        assembler.ingest(
            obs(
                1.2,
                "player",
                ObservationKind.MELD_DELTA,
                tiles=("E", "E", "E"),
            )
        )
        actions = assembler.advance_time(1.7)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].kind, PublicActionKind.UNKNOWN_ACTION)
        self.assertEqual(
            actions[0].unknown_reasons,
            ("multiple_claim_evidence_combinations",),
        )

    def test_claim_window_does_not_reuse_stale_discard(self):
        assembler = TemporalActionAssembler(self.config)
        assembler.ingest(
            obs(1.0, "opponent", ObservationKind.DISCARD, tile="P5")
        )
        assembler.ingest(
            obs(
                4.2,
                "player",
                ObservationKind.HAND_DELTA,
                details={"removed_tiles": ["P3", "P4"]},
            )
        )
        assembler.ingest(
            obs(
                4.3,
                "player",
                ObservationKind.MELD_DELTA,
                tiles=("P3", "P4", "P5"),
            )
        )
        actions = assembler.advance_time(7.31)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].kind, PublicActionKind.UNKNOWN_ACTION)

    def test_consumed_discard_is_not_reused_for_second_claim(self):
        assembler = TemporalActionAssembler(self.config)
        assembler.ingest(
            obs(1.0, "opponent", ObservationKind.DISCARD, tile="E")
        )
        assembler.ingest(
            obs(
                1.1,
                "player",
                ObservationKind.HAND_DELTA,
                details={"removed_tiles": ["E", "E"]},
            )
        )
        assembler.ingest(
            obs(
                1.2,
                "player",
                ObservationKind.MELD_DELTA,
                tiles=("E", "E", "E"),
            )
        )
        first = assembler.advance_time(1.7)
        self.assertEqual(first[0].kind, PublicActionKind.PENG)

        assembler.ingest(
            obs(
                2.0,
                "player",
                ObservationKind.HAND_DELTA,
                details={"removed_tiles": ["E", "E"]},
            )
        )
        assembler.ingest(
            obs(
                2.1,
                "player",
                ObservationKind.MELD_DELTA,
                tiles=("E", "E", "E"),
            )
        )
        second = assembler.advance_time(5.11)
        self.assertEqual(len(second), 1)
        self.assertEqual(second[0].kind, PublicActionKind.UNKNOWN_ACTION)

    def test_direct_hu_remains_unknown_subtype_when_not_observed(self):
        assembler = TemporalActionAssembler(self.config)
        actions = assembler.ingest(
            obs(9.0, "player", ObservationKind.HU)
        )
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].kind, PublicActionKind.HU)
        self.assertEqual(actions[0].evidence_grade, EvidenceGrade.UNKNOWN)
        self.assertEqual(
            actions[0].unknown_reasons,
            ("hu_subtype_unconfirmed",),
        )

    def test_flush_expires_unresolved_meld(self):
        assembler = TemporalActionAssembler(self.config)
        assembler.ingest(
            obs(
                2.0,
                "player",
                ObservationKind.MELD_DELTA,
                tiles=("P3", "P4", "P5"),
            )
        )
        actions = assembler.flush()
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].kind, PublicActionKind.UNKNOWN_ACTION)

    def test_input_timestamp_must_not_move_backwards(self):
        assembler = TemporalActionAssembler(self.config)
        assembler.ingest(
            obs(2.0, "player", ObservationKind.DISCARD, tile="M1")
        )
        with self.assertRaises(ValueError):
            assembler.ingest(
                obs(1.9, "opponent", ObservationKind.DISCARD, tile="M2")
            )


class CaptureScopeActionAssemblerTests(unittest.TestCase):
    """Distinct video sources may share timestamps, tile IDs and actor labels."""

    def setUp(self) -> None:
        self.assembler = TemporalActionAssembler(
            AssemblyConfig(claim_window_seconds=3.0, assembly_delay_seconds=0.4)
        )

    @staticmethod
    def scoped(
        t: float,
        actor: str,
        kind: ObservationKind,
        session: str,
        epoch: int = 0,
        *,
        tile: str | None = None,
        tiles: tuple[str, ...] = (),
        refs: tuple[str, ...] = (),
        extra: dict | None = None,
    ) -> RawObservation:
        return obs(
            t,
            actor,
            kind,
            tile=tile,
            tiles=tiles,
            refs=refs,
            details={
                "source_session": session,
                "stream_epoch": epoch,
                **(extra or {}),
            },
        )

    def test_same_session_epoch_still_reconstructs_claimed_chi(self):
        self.assembler.ingest(
            self.scoped(1.0, "opponent", ObservationKind.DISCARD, "session-a",
                        tile="P5", refs=("a:discard",))
        )
        self.assembler.ingest(
            self.scoped(1.2, "player", ObservationKind.MELD_DELTA, "session-a",
                        tiles=("P3", "P4", "P5"), refs=("a:meld",))
        )
        self.assembler.ingest(
            self.scoped(1.3, "player", ObservationKind.HAND_DELTA, "session-a",
                        refs=("a:hand",),
                        extra={"removed_tiles": ["P3", "P4"]})
        )
        actions = self.assembler.advance_time(1.7)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].kind, PublicActionKind.CHI)
        self.assertEqual(
            set(actions[0].evidence_refs),
            {"a:discard", "a:meld", "a:hand"},
        )

    def test_session_change_expires_meld_and_never_uses_new_source_hand(self):
        self.assembler.ingest(
            self.scoped(5.0, "opponent", ObservationKind.DISCARD, "session-a",
                        tile="P5", refs=("a:discard",))
        )
        self.assembler.ingest(
            self.scoped(5.1, "player", ObservationKind.MELD_DELTA, "session-a",
                        tiles=("P3", "P4", "P5"), refs=("a:meld",))
        )
        # Session B restarts its relative clock; no backwards-time error.
        actions = self.assembler.ingest(
            self.scoped(0.1, "player", ObservationKind.HAND_DELTA, "session-b",
                        refs=("b:hand",),
                        extra={"removed_tiles": ["P3", "P4"]})
        )
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].kind, PublicActionKind.UNKNOWN_ACTION)
        self.assertEqual(
            actions[0].unknown_reasons, ("capture_scope_discontinuity",)
        )
        self.assertEqual(set(actions[0].evidence_refs), {"a:discard", "a:meld"})
        self.assertEqual(actions[0].details["previous_source_session"], "session-a")
        self.assertEqual(actions[0].details["next_source_session"], "session-b")
        self.assertEqual(self.assembler.advance_time(4.0), ())

    def test_epoch_change_prevents_cross_gap_claim_and_add_kong(self):
        self.assembler.ingest(
            self.scoped(1.0, "player", ObservationKind.HAND_DELTA, "session-a",
                        refs=("epoch0:hand",),
                        extra={"removed_tiles": ["E"]})
        )
        self.assembler.ingest(
            self.scoped(1.1, "player", ObservationKind.MELD_DELTA, "session-a",
                        tiles=("E", "E", "E", "E"), refs=("epoch0:meld",),
                        extra={"previous_meld": ["E", "E", "E"]})
        )
        changed = self.assembler.ingest(
            self.scoped(1.2, "player", ObservationKind.HAND_DELTA, "session-a",
                        epoch=1, refs=("epoch1:hand",),
                        extra={"removed_tiles": ["E"]})
        )
        self.assertEqual([x.kind for x in changed], [PublicActionKind.UNKNOWN_ACTION])
        self.assertEqual(changed[0].details["next_stream_epoch"], 1)
        self.assertNotIn("epoch1:hand", changed[0].evidence_refs)

    def test_missing_source_metadata_never_joins_scoped_observations(self):
        self.assembler.ingest(
            self.scoped(2.0, "opponent", ObservationKind.DISCARD, "session-a",
                        tile="S6")
        )
        self.assembler.ingest(
            self.scoped(2.1, "player", ObservationKind.MELD_DELTA, "session-a",
                        tiles=("S4", "S5", "S6"))
        )
        actions = self.assembler.ingest(
            obs(2.2, "player", ObservationKind.HAND_DELTA,
                details={"removed_count": 2})
        )
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].unknown_reasons,
                         ("capture_scope_discontinuity",))

    def test_invalid_capture_lineage_rejected_before_mutating_pending(self):
        self.assembler.ingest(
            self.scoped(1.0, "opponent", ObservationKind.DISCARD, "session-a",
                        tile="P5")
        )
        for invalid in (
            {"source_session": "", "stream_epoch": 0},
            {"source_session": "session-a", "stream_epoch": True},
            {"source_session": "session-a", "stream_epoch": -1},
            {"source_session": 7, "stream_epoch": 0},
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    self.assembler.ingest(
                        obs(1.1, "player", ObservationKind.HAND_DELTA,
                            details=invalid)
                    )
        self.assertEqual(self.assembler.watermark, 1.0)

    def test_same_source_clock_must_remain_monotonic(self):
        self.assembler.ingest(
            self.scoped(3.0, "opponent", ObservationKind.DISCARD, "session-a",
                        tile="P5")
        )
        with self.assertRaisesRegex(ValueError, "nondecreasing"):
            self.assembler.ingest(
                self.scoped(2.9, "player", ObservationKind.HAND_DELTA,
                            "session-a", extra={"removed_count": 2})
            )

    def test_epoch_change_allows_clock_reset_without_false_claim(self):
        self.assembler.ingest(
            self.scoped(8.0, "opponent", ObservationKind.DISCARD, "session-a",
                        tile="S6")
        )
        self.assertEqual(
            self.assembler.ingest(
                self.scoped(0.1, "player", ObservationKind.HAND_DELTA,
                            "session-a", epoch=1,
                            extra={"removed_count": 2})
            ),
            (),
        )
        self.assertEqual(self.assembler.watermark, 0.1)


if __name__ == "__main__":
    unittest.main()
