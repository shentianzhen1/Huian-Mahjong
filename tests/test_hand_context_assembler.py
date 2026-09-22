from __future__ import annotations

import unittest

from workspace.vision.hand_context_assembler import (
    DealerEvidence,
    assemble_hand_context,
)
from workspace.vision.public_match_reconstruction import (
    ObservationKind,
    RawObservation,
)
from workspace.vision.tiles_v0_1.public_state import PublicStateObservation


def state(
    *,
    top_right: int | None = 1000,
    bottom_left: int | None = 1000,
    hand: int | None = 1,
    remaining: int | None = 120,
    issues: tuple[str, ...] = (),
) -> PublicStateObservation:
    return PublicStateObservation(
        top_right_score=top_right,
        bottom_left_score=bottom_left,
        hand_number=hand,
        remaining_tiles=remaining,
        score_votes=3 if top_right is not None and bottom_left is not None else 0,
        hand_votes=3 if hand is not None else 0,
        remaining_votes=3 if remaining is not None else 0,
        issues=issues,
        safe_for_executor=False,
    )


def gold(
    ts: float,
    tile: str | None,
    *,
    confidence: float = 0.99,
    ref: str,
) -> RawObservation:
    return RawObservation(
        timestamp_seconds=ts,
        actor="system",
        kind=ObservationKind.GOLD,
        tile=tile,
        confidence=confidence,
        evidence_refs=(ref,),
    )


class HandContextAssemblerTests(unittest.TestCase):
    def test_complete_header_maps_bottom_left_score_to_player_seat_zero(self):
        draft = assemble_hand_context(
            state(top_right=900, bottom_left=1100, hand=3),
            player_seat=0,
            dealer_evidence=(
                DealerEvidence(1.0, 1, evidence_refs=("dealer:a",)),
                DealerEvidence(1.1, 1, evidence_refs=("dealer:b",)),
            ),
            gold_observations=(
                gold(1.5, "M1", ref="gold:a"),
                gold(1.6, "M1", ref="gold:b"),
            ),
            public_state_evidence_refs=("status:a",),
            public_state_timestamp_seconds=0.8,
            room_options=("single_gold_no_ron_pinghu",),
        )
        self.assertEqual(draft.hand_index, 3)
        self.assertEqual(draft.context.player_seat, 0)
        self.assertEqual(draft.context.dealer, 1)
        self.assertEqual(draft.context.initial_scores, (1100, 900))
        self.assertEqual(draft.context.gold_tile, "M1")
        self.assertIsNone(draft.context.current_dealer_base)
        self.assertTrue(draft.complete_for_ledger_header)
        self.assertEqual(draft.issues, ())
        self.assertEqual(
            set(draft.evidence_refs),
            {"status:a", "dealer:a", "dealer:b", "gold:a", "gold:b"},
        )

    def test_score_mapping_respects_player_seat_one(self):
        draft = assemble_hand_context(
            state(top_right=700, bottom_left=1300, hand=2),
            player_seat=1,
            dealer_evidence=(
                DealerEvidence(1.0, 0),
                DealerEvidence(1.1, 0),
            ),
            gold_observations=(
                gold(1.5, "S3", ref="g1"),
                gold(1.6, "S3", ref="g2"),
            ),
        )
        self.assertEqual(draft.context.initial_scores, (700, 1300))
        self.assertEqual(draft.context.dealer, 0)

    def test_score_order_is_not_guessed_without_player_seat(self):
        draft = assemble_hand_context(
            state(top_right=900, bottom_left=1100, hand=1),
            player_seat=None,
            dealer_evidence=(
                DealerEvidence(1.0, 0),
                DealerEvidence(1.1, 0),
            ),
            gold_observations=(
                gold(1.5, "P3", ref="g1"),
                gold(1.6, "P3", ref="g2"),
            ),
        )
        self.assertIsNone(draft.context.initial_scores)
        self.assertIn("player_seat_unknown", draft.issues)
        self.assertFalse(draft.complete_for_ledger_header)

    def test_dealer_requires_consensus_and_is_never_inferred_from_scores(self):
        draft = assemble_hand_context(
            state(top_right=1300, bottom_left=700, hand=4),
            player_seat=0,
            dealer_evidence=(
                DealerEvidence(1.0, 0, evidence_refs=("d0",)),
                DealerEvidence(1.1, 1, evidence_refs=("d1",)),
            ),
            gold_observations=(
                gold(1.5, "P5", ref="g1"),
                gold(1.6, "P5", ref="g2"),
            ),
        )
        self.assertIsNone(draft.context.dealer)
        self.assertIn("dealer_consensus", draft.issues)
        self.assertIsNone(draft.context.current_dealer_base)

    def test_gold_requires_consensus_and_conflict_stays_unknown(self):
        draft = assemble_hand_context(
            state(hand=5),
            player_seat=0,
            dealer_evidence=(
                DealerEvidence(1.0, 1),
                DealerEvidence(1.1, 1),
            ),
            gold_observations=(
                gold(1.5, "M1", ref="g1"),
                gold(1.6, "P1", ref="g2"),
            ),
        )
        self.assertIsNone(draft.context.gold_tile)
        self.assertIn("gold_consensus", draft.issues)

    def test_low_confidence_opening_evidence_is_ignored(self):
        draft = assemble_hand_context(
            state(hand=6),
            player_seat=0,
            dealer_evidence=(
                DealerEvidence(1.0, 1, confidence=0.4),
                DealerEvidence(1.1, 1, confidence=0.4),
            ),
            gold_observations=(
                gold(1.5, "M1", confidence=0.4, ref="g1"),
                gold(1.6, "M1", confidence=0.4, ref="g2"),
            ),
            minimum_confidence=0.8,
        )
        self.assertIsNone(draft.context.dealer)
        self.assertIsNone(draft.context.gold_tile)
        self.assertIn("dealer_unreadable", draft.issues)
        self.assertIn("gold_unreadable", draft.issues)

    def test_public_state_unknowns_remain_explicit(self):
        draft = assemble_hand_context(
            state(
                top_right=None,
                bottom_left=None,
                hand=None,
                remaining=None,
                issues=("score_unreadable", "hand_unreadable"),
            ),
            player_seat=0,
        )
        self.assertIsNone(draft.hand_index)
        self.assertIsNone(draft.context.initial_scores)
        self.assertIsNone(draft.context.dealer)
        self.assertIsNone(draft.context.gold_tile)
        self.assertIn("hand_index_unknown", draft.issues)
        self.assertIn("initial_scores_unknown", draft.issues)
        self.assertIn("public_state:score_unreadable", draft.issues)
        self.assertIn("public_state:hand_unreadable", draft.issues)

    def test_opening_actions_create_hand_start_and_gold_in_time_order(self):
        draft = assemble_hand_context(
            state(hand=7),
            player_seat=0,
            dealer_evidence=(
                DealerEvidence(0.5, 0, evidence_refs=("d1",)),
                DealerEvidence(0.6, 0, evidence_refs=("d2",)),
            ),
            gold_observations=(
                gold(2.0, "N", ref="g1"),
                gold(2.1, "N", ref="g2"),
            ),
            public_state_evidence_refs=("status",),
            public_state_timestamp_seconds=0.4,
        )
        actions = draft.opening_actions()
        self.assertEqual([item.kind.value for item in actions], ["HAND_START", "OPEN_GOLD"])
        self.assertEqual(actions[0].timestamp_seconds, 0.4)
        self.assertEqual(actions[1].timestamp_seconds, 2.0)
        self.assertEqual(actions[1].tile, "N")

        events = [action.to_timeline_event() for action in actions]
        self.assertTrue(all(event.evidence_level == "unknown" for event in events))
        self.assertEqual(events[0].details["hand_index"], 7)

    def test_no_hand_start_action_when_hand_index_is_unknown(self):
        draft = assemble_hand_context(
            state(hand=None),
            player_seat=0,
            dealer_evidence=(
                DealerEvidence(0.5, 0),
                DealerEvidence(0.6, 0),
            ),
            gold_observations=(
                gold(2.0, "N", ref="g1"),
                gold(2.1, "N", ref="g2"),
            ),
        )
        actions = draft.opening_actions()
        self.assertEqual([item.kind.value for item in actions], ["OPEN_GOLD"])


if __name__ == "__main__":
    unittest.main()
