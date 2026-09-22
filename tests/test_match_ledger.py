from __future__ import annotations

import unittest

from huian.evidence.timeline import HandContext, HandSettlement, HandTimeline, TimelineEvent
from workspace.vision.match_ledger import (
    build_match_ledger_index,
    hand_timeline_draft_from_actions,
    render_hand_ledger_zh,
    render_match_ledger_zh,
    tile_zh,
)
from workspace.vision.public_match_reconstruction import (
    EvidenceGrade,
    ObservationKind,
    PublicActionKind,
    RawObservation,
    ReconstructedAction,
    direct_action,
    reconstruct_claimed_meld,
)


def event(
    t: float,
    actor: str,
    kind: str,
    *,
    tile: str | None = None,
    details: dict | None = None,
    evidence_level: str = "unknown",
    result: str | None = None,
) -> TimelineEvent:
    return TimelineEvent(
        timestamp_seconds=t,
        actor=actor,
        kind=kind,
        evidence_level=evidence_level,
        tile=tile,
        result=result,
        details=details or {},
    )


def timeline(
    hand_index: int,
    *,
    player_seat: int = 0,
    dealer: int = 1,
    gold: str | None = "SOUTH",
    initial_scores: tuple[int, int] = (1000, 1000),
    events: tuple[TimelineEvent, ...] = (),
    settlement: HandSettlement | None = None,
    evidence_id: str | None = None,
) -> HandTimeline:
    return HandTimeline(
        evidence_id=evidence_id or f"hand_{hand_index}",
        hand_index=hand_index,
        source_sha256=None,
        duration_seconds=120.0,
        geometry="1046x480",
        context=HandContext(
            player_seat=player_seat,
            dealer=dealer,
            initial_scores=initial_scores,
            gold_tile=gold,
        ),
        events=events,
        settlement=settlement or HandSettlement(),
    )


class TileZhTests(unittest.TestCase):
    def test_suited_honors_and_unknown(self):
        self.assertEqual(tile_zh("M9"), "9万")
        self.assertEqual(tile_zh("P5"), "5筒")
        self.assertEqual(tile_zh("S1"), "1条")
        self.assertEqual(tile_zh("SOUTH"), "南")
        self.assertEqual(tile_zh("B"), "白")
        self.assertEqual(tile_zh(None), "未知牌")


class HandLedgerTests(unittest.TestCase):
    def test_renders_requested_public_hand_flow(self):
        hand = timeline(
            1,
            dealer=1,
            gold="SOUTH",
            events=(
                event(0.0, "system", "HAND_START"),
                event(3.2, "system", "OPEN_GOLD", tile="SOUTH"),
                event(6.8, "opponent", "DISCARD", tile="M9"),
                event(12.4, "opponent", "DISCARD", tile="P5"),
                event(
                    13.0,
                    "player",
                    "CHI",
                    tile="P5",
                    details={
                        "claimed_tile": "P5",
                        "meld": ["P3", "P4", "P5"],
                        "consumed_from_hand": ["P3", "P4"],
                    },
                ),
                event(14.3, "player", "DISCARD", tile="E"),
                event(
                    52.3,
                    "player",
                    "YOUJIN_STATE",
                    details={"state": "YOUJIN"},
                ),
                event(
                    59.1,
                    "player",
                    "YOUJIN_STATE",
                    details={"state": "DOUBLE_YOU"},
                ),
                event(
                    74.5,
                    "player",
                    "HU",
                    details={"subtype": "DOUBLE_YOU"},
                ),
                event(77.0, "system", "SETTLEMENT"),
            ),
            settlement=HandSettlement(
                winner=0,
                win_type="DOUBLE_YOU",
                fan=3,
                multiplier=8,
                dealer_base=30,
                net_score=264,
                scores_before=(1000, 1000),
                scores_after=(1264, 736),
                evidence_level="unknown",
            ),
        )
        rendered = render_hand_ledger_zh(hand)

        self.assertIn("## 第 1/8 局", rendered)
        self.assertIn("庄家：对手 ｜ 金：南", rendered)
        self.assertIn("00:06.8  对手出牌：9万", rendered)
        self.assertIn("00:13.0  我方吃：3筒 4筒 5筒（吃 5筒）", rendered)
        self.assertIn("00:52.3  我方状态：游金中", rendered)
        self.assertIn("00:59.1  我方状态：双游中", rendered)
        self.assertIn("01:14.5  我方胡牌：双游", rendered)
        self.assertIn("- 倍率：×8", rendered)
        self.assertIn("- 赢家净分：+264", rendered)
        self.assertIn("- 结算后比分：我方 1264 ｜ 对手 736", rendered)

    def test_unknown_hu_subtype_stays_explicit(self):
        hand = timeline(
            2,
            events=(
                event(40.0, "opponent", "HU"),
            ),
        )
        rendered = render_hand_ledger_zh(hand)
        self.assertIn("对手胡牌：胡法待确认", rendered)
        self.assertIn("结算：待确认", rendered)

    def test_unknown_gold_stays_explicit(self):
        hand = timeline(3, gold=None)
        rendered = render_hand_ledger_zh(hand)
        self.assertIn("金：待确认", rendered)

    def test_player_dealer_mapping_uses_player_seat(self):
        hand = timeline(4, player_seat=1, dealer=1)
        rendered = render_hand_ledger_zh(hand)
        self.assertIn("庄家：我方", rendered)

    def test_audit_view_keeps_machine_grade_separate_from_timeline_evidence(self):
        hand = timeline(
            1,
            events=(
                event(
                    10.0,
                    "player",
                    "PENG",
                    details={
                        "meld": ["E", "E", "E"],
                        "claimed_tile": "E",
                        "reconstruction_evidence_grade": "CORROBORATED",
                        "reconstruction_confidence": 0.97,
                    },
                ),
            ),
        )
        rendered = render_hand_ledger_zh(hand, audit=True)
        self.assertIn("timeline=unknown", rendered)
        self.assertIn("machine=CORROBORATED", rendered)
        self.assertIn("confidence=0.97", rendered)

    def test_unknown_action_reason_is_visible(self):
        hand = timeline(
            1,
            events=(
                event(
                    20.0,
                    "player",
                    "UNKNOWN_ACTION",
                    details={
                        "reconstruction_unknown_reasons": [
                            "meld_window_expired_without_unique_reconstruction"
                        ]
                    },
                ),
            ),
        )
        rendered = render_hand_ledger_zh(hand)
        self.assertIn("我方动作待确认", rendered)
        self.assertIn(
            "meld_window_expired_without_unique_reconstruction",
            rendered,
        )


class MatchLedgerTests(unittest.TestCase):
    def test_partial_match_lists_missing_hands(self):
        first = timeline(
            1,
            settlement=HandSettlement(
                winner=0,
                net_score=100,
                scores_before=(1000, 1000),
                scores_after=(1100, 900),
            ),
        )
        second = timeline(
            2,
            initial_scores=(1100, 900),
            settlement=HandSettlement(
                winner=1,
                net_score=50,
                scores_before=(1100, 900),
                scores_after=(1050, 950),
            ),
        )
        rendered = render_match_ledger_zh((first, second))
        self.assertIn("已记录：2/8 局", rendered)
        self.assertIn("缺失局：3、4、5、6、7、8", rendered)
        self.assertIn("起始比分：我方 1000 ｜ 对手 1000", rendered)
        self.assertIn("当前/最终比分：我方 1050 ｜ 对手 950", rendered)

    def test_score_continuity_conflict_is_not_silenced(self):
        first = timeline(
            1,
            settlement=HandSettlement(
                scores_after=(1100, 900),
            ),
        )
        second = timeline(
            2,
            initial_scores=(1000, 1000),
        )
        index = build_match_ledger_index((first, second))
        self.assertEqual(
            index.score_continuity_issues,
            ("hand_1_scores_after_!=_hand_2_initial_scores",),
        )
        self.assertFalse(index.complete)

    def test_duplicate_hand_index_is_rejected(self):
        with self.assertRaises(ValueError):
            build_match_ledger_index(
                (
                    timeline(1, evidence_id="a"),
                    timeline(1, evidence_id="b"),
                )
            )

    def test_complete_eight_hand_index(self):
        hands = tuple(timeline(index) for index in range(1, 9))
        index = build_match_ledger_index(hands)
        self.assertEqual(index.missing_hands, ())
        self.assertEqual(index.score_continuity_issues, ())
        self.assertTrue(index.complete)


class ActionToTimelineDraftTests(unittest.TestCase):
    def test_reconstructed_actions_become_sorted_unknown_only_timeline(self):
        discard = direct_action(
            RawObservation(
                timestamp_seconds=10.0,
                actor="opponent",
                kind=ObservationKind.DISCARD,
                tile="P5",
                evidence_refs=("river:P5",),
            )
        )
        chi = reconstruct_claimed_meld(
            RawObservation(
                10.0,
                "opponent",
                ObservationKind.DISCARD,
                tile="P5",
            ),
            RawObservation(
                10.2,
                "player",
                ObservationKind.HAND_DELTA,
                details={"removed_tiles": ["P3", "P4"]},
            ),
            RawObservation(
                10.3,
                "player",
                ObservationKind.MELD_DELTA,
                tiles=("P3", "P4", "P5"),
            ),
        )
        self.assertEqual(chi.kind, PublicActionKind.CHI)
        self.assertEqual(chi.evidence_grade, EvidenceGrade.CORROBORATED)

        hand = hand_timeline_draft_from_actions(
            evidence_id="draft_1",
            hand_index=1,
            actions=(chi, discard),
            context=HandContext(
                player_seat=0,
                dealer=1,
                initial_scores=(1000, 1000),
                gold_tile="M1",
            ),
        )
        self.assertEqual(
            tuple(item.kind for item in hand.events),
            ("DISCARD", "CHI"),
        )
        self.assertTrue(
            all(item.evidence_level == "unknown" for item in hand.events)
        )

        rendered = render_hand_ledger_zh(hand)
        self.assertIn("对手出牌：5筒", rendered)
        self.assertIn("我方吃：3筒 4筒 5筒", rendered)


if __name__ == "__main__":
    unittest.main()
