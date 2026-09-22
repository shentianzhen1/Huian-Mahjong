from __future__ import annotations

import unittest

from workspace.vision.public_match_reconstruction import (
    EvidenceGrade,
    ObservationKind,
    PublicActionKind,
    RawObservation,
    direct_action,
    reconstruct_add_kong,
    reconstruct_claimed_meld,
)


class PublicMatchReconstructionTests(unittest.TestCase):
    def test_open_gold_is_direct_and_timeline_ready(self):
        observation = RawObservation(
            3.2,
            "system",
            ObservationKind.GOLD,
            tile="SOUTH",
            confidence=0.99,
            evidence_refs=("frame:96",),
        )
        action = direct_action(observation)
        self.assertEqual(action.kind, PublicActionKind.OPEN_GOLD)
        self.assertEqual(action.evidence_grade, EvidenceGrade.DIRECT)
        event = action.to_timeline_event()
        self.assertEqual(event.kind, "OPEN_GOLD")
        self.assertEqual(event.tile, "SOUTH")
        self.assertEqual(event.evidence_level, "direct_observation")

    def test_unknown_gold_stays_unknown(self):
        action = direct_action(RawObservation(3.2, "system", ObservationKind.GOLD))
        self.assertEqual(action.evidence_grade, EvidenceGrade.UNKNOWN)
        self.assertEqual(action.unknown_reasons, ("gold_tile_unknown",))

    def test_chi_requires_discard_hand_delta_and_meld_delta(self):
        discard = RawObservation(
            12.4,
            "opponent",
            ObservationKind.DISCARD,
            tile="P5",
            confidence=0.98,
            evidence_refs=("discard:372",),
        )
        hand_delta = RawObservation(
            12.8,
            "player",
            ObservationKind.HAND_DELTA,
            confidence=0.97,
            evidence_refs=("hand:384",),
            details={"removed_tiles": ["P3", "P4"]},
        )
        meld_delta = RawObservation(
            13.0,
            "player",
            ObservationKind.MELD_DELTA,
            confidence=0.96,
            tiles=("P3", "P4", "P5"),
            evidence_refs=("meld:390",),
        )
        action = reconstruct_claimed_meld(discard, hand_delta, meld_delta)
        self.assertEqual(action.kind, PublicActionKind.CHI)
        self.assertEqual(action.evidence_grade, EvidenceGrade.CORROBORATED)
        self.assertEqual(action.claimed_tile, "P5")
        self.assertEqual(action.consumed_from_hand, ("P3", "P4"))
        self.assertEqual(action.meld, ("P3", "P4", "P5"))
        self.assertEqual(action.confidence, 0.96)

    def test_peng_is_reconstructed_from_matching_counts(self):
        action = reconstruct_claimed_meld(
            RawObservation(1.0, "player", ObservationKind.DISCARD, tile="E"),
            RawObservation(
                1.2,
                "opponent",
                ObservationKind.HAND_DELTA,
                details={"removed_tiles": ["E", "E"]},
            ),
            RawObservation(
                1.3,
                "opponent",
                ObservationKind.MELD_DELTA,
                tiles=("E", "E", "E"),
            ),
        )
        self.assertEqual(action.kind, PublicActionKind.PENG)

    def test_ming_gang_is_reconstructed_from_discard_and_three_removed_tiles(self):
        action = reconstruct_claimed_meld(
            RawObservation(1.0, "opponent", ObservationKind.DISCARD, tile="P7"),
            RawObservation(
                1.2,
                "player",
                ObservationKind.HAND_DELTA,
                details={"removed_tiles": ["P7", "P7", "P7"]},
            ),
            RawObservation(
                1.3,
                "player",
                ObservationKind.MELD_DELTA,
                tiles=("P7", "P7", "P7", "P7"),
            ),
        )
        self.assertEqual(action.kind, PublicActionKind.MING_GANG)

    def test_conflicting_hand_delta_fails_closed(self):
        action = reconstruct_claimed_meld(
            RawObservation(1.0, "opponent", ObservationKind.DISCARD, tile="P5"),
            RawObservation(
                1.1,
                "player",
                ObservationKind.HAND_DELTA,
                details={"removed_tiles": ["P2", "P4"]},
            ),
            RawObservation(
                1.2,
                "player",
                ObservationKind.MELD_DELTA,
                tiles=("P3", "P4", "P5"),
            ),
        )
        self.assertEqual(action.kind, PublicActionKind.EVIDENCE_CONFLICT)
        self.assertEqual(action.evidence_grade, EvidenceGrade.UNKNOWN)
        self.assertEqual(
            action.unknown_reasons,
            ("hand_delta_does_not_match_claimed_meld",),
        )

    def test_missing_consumed_tiles_remains_unknown(self):
        action = reconstruct_claimed_meld(
            RawObservation(1.0, "opponent", ObservationKind.DISCARD, tile="P5"),
            RawObservation(1.1, "player", ObservationKind.HAND_DELTA),
            RawObservation(
                1.2,
                "player",
                ObservationKind.MELD_DELTA,
                tiles=("P3", "P4", "P5"),
            ),
        )
        self.assertEqual(action.kind, PublicActionKind.UNKNOWN_ACTION)
        self.assertEqual(action.unknown_reasons, ("consumed_hand_delta_unknown",))


    def test_opponent_chi_can_use_concealed_count_delta_without_hidden_tile_ids(self):
        action = reconstruct_claimed_meld(
            RawObservation(
                20.0,
                "player",
                ObservationKind.DISCARD,
                tile="S6",
                confidence=0.99,
            ),
            RawObservation(
                20.3,
                "opponent",
                ObservationKind.HAND_DELTA,
                confidence=0.96,
                details={"removed_count": 2},
            ),
            RawObservation(
                20.5,
                "opponent",
                ObservationKind.MELD_DELTA,
                confidence=0.97,
                tiles=("S4", "S5", "S6"),
            ),
        )
        self.assertEqual(action.kind, PublicActionKind.CHI)
        self.assertEqual(action.evidence_grade, EvidenceGrade.CORROBORATED)
        self.assertEqual(action.consumed_from_hand, ("S4", "S5"))
        self.assertFalse(action.details["hand_delta_identity_observed"])
        self.assertEqual(action.details["removed_count"], 2)

    def test_opponent_meld_count_conflict_fails_closed(self):
        action = reconstruct_claimed_meld(
            RawObservation(20.0, "player", ObservationKind.DISCARD, tile="S6"),
            RawObservation(
                20.3,
                "opponent",
                ObservationKind.HAND_DELTA,
                details={"removed_count": 1},
            ),
            RawObservation(
                20.5,
                "opponent",
                ObservationKind.MELD_DELTA,
                tiles=("S4", "S5", "S6"),
            ),
        )
        self.assertEqual(action.kind, PublicActionKind.EVIDENCE_CONFLICT)
        self.assertEqual(
            action.unknown_reasons,
            ("hand_count_delta_does_not_match_claimed_meld",),
        )

    def test_add_kong_requires_explicit_previous_peng(self):
        action = reconstruct_add_kong(
            RawObservation(
                4.0,
                "player",
                ObservationKind.HAND_DELTA,
                details={"removed_tiles": ["S8"]},
            ),
            RawObservation(
                4.1,
                "player",
                ObservationKind.MELD_DELTA,
                tiles=("S8", "S8", "S8", "S8"),
                details={"previous_meld": ["S8", "S8", "S8"]},
            ),
        )
        self.assertEqual(action.kind, PublicActionKind.ADD_KONG)
        self.assertEqual(action.evidence_grade, EvidenceGrade.CORROBORATED)

    def test_four_tile_meld_without_previous_peng_does_not_guess_kong_type(self):
        action = reconstruct_add_kong(
            RawObservation(
                4.0,
                "player",
                ObservationKind.HAND_DELTA,
                details={"removed_tiles": ["S8"]},
            ),
            RawObservation(
                4.1,
                "player",
                ObservationKind.MELD_DELTA,
                tiles=("S8", "S8", "S8", "S8"),
            ),
        )
        self.assertEqual(action.kind, PublicActionKind.UNKNOWN_ACTION)

    def test_youjin_state_can_be_recorded_without_rule_inference(self):
        action = direct_action(
            RawObservation(
                52.3,
                "player",
                ObservationKind.YOUJIN_STATE,
                confidence=0.99,
                details={"state": "YOUJIN", "result": "Youjin active"},
            )
        )
        self.assertEqual(action.kind, PublicActionKind.YOUJIN_STATE)
        self.assertEqual(action.evidence_grade, EvidenceGrade.DIRECT)
        self.assertEqual(action.details["state"], "YOUJIN")

    def test_hu_without_subtype_does_not_guess(self):
        action = direct_action(
            RawObservation(
                70.0,
                "player",
                ObservationKind.HU,
                confidence=0.95,
            )
        )
        self.assertEqual(action.kind, PublicActionKind.HU)
        self.assertEqual(action.evidence_grade, EvidenceGrade.UNKNOWN)
        self.assertEqual(action.unknown_reasons, ("hu_subtype_unconfirmed",))
        event = action.to_timeline_event()
        self.assertEqual(event.evidence_level, "unknown")
        self.assertEqual(
            event.details["reconstruction_unknown_reasons"],
            ["hu_subtype_unconfirmed"],
        )


if __name__ == "__main__":
    unittest.main()
