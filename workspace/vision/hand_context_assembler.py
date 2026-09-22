"""Assemble read-only hand opening context from public observations.

This module bridges PublicState / dealer-marker evidence / Gold evidence into the
canonical HandContext used by HandTimeline and Match Ledger.

It deliberately does not infer dealer from score, turn order, or Mahjong rules.
Unknown opening facts remain unknown.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from huian.evidence.timeline import HandContext
from workspace.vision.public_match_reconstruction import (
    ObservationKind,
    RawObservation,
    ReconstructedAction,
    direct_action,
)
from workspace.vision.tiles_v0_1.public_state import PublicStateObservation


@dataclass(frozen=True)
class DealerEvidence:
    timestamp_seconds: float
    dealer_seat: int | None
    confidence: float = 1.0
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            isinstance(self.timestamp_seconds, bool)
            or not isinstance(self.timestamp_seconds, (int, float))
            or self.timestamp_seconds < 0
        ):
            raise ValueError("timestamp_seconds must be nonnegative numeric")
        if self.dealer_seat is not None and (
            type(self.dealer_seat) is not int or self.dealer_seat not in (0, 1)
        ):
            raise ValueError("dealer_seat must be seat 0, seat 1 or None")
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not 0 <= float(self.confidence) <= 1
        ):
            raise ValueError("confidence must be within [0, 1]")
        object.__setattr__(self, "timestamp_seconds", float(self.timestamp_seconds))
        object.__setattr__(self, "confidence", float(self.confidence))
        object.__setattr__(
            self,
            "evidence_refs",
            tuple(str(ref) for ref in self.evidence_refs if str(ref)),
        )


@dataclass(frozen=True)
class HandContextDraft:
    hand_index: int | None
    context: HandContext
    issues: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    hand_start_timestamp_seconds: float | None = None
    gold_timestamp_seconds: float | None = None
    safe_for_hint: bool = False
    safe_for_executor: bool = False

    @property
    def complete_for_ledger_header(self) -> bool:
        return (
            self.hand_index is not None
            and self.context.player_seat is not None
            and self.context.dealer is not None
            and self.context.initial_scores is not None
            and self.context.gold_tile is not None
        )

    def opening_actions(self) -> tuple[ReconstructedAction, ...]:
        """Create UNKNOWN-only-compatible opening actions for HandTimeline.

        ReconstructedAction.to_timeline_event() keeps canonical timeline
        evidence_level=unknown, so machine opening facts do not auto-confirm
        rule evidence.
        """
        actions: list[ReconstructedAction] = []
        if self.hand_index is not None and self.hand_start_timestamp_seconds is not None:
            actions.append(
                direct_action(
                    RawObservation(
                        timestamp_seconds=self.hand_start_timestamp_seconds,
                        actor="system",
                        kind=ObservationKind.HAND_START,
                        confidence=1.0,
                        evidence_refs=self.evidence_refs,
                        details={
                            "hand_index": self.hand_index,
                            "dealer": self.context.dealer,
                            "initial_scores": (
                                list(self.context.initial_scores)
                                if self.context.initial_scores is not None
                                else None
                            ),
                            "source": "hand_context_assembler_v0_1",
                        },
                    )
                )
            )
        if self.context.gold_tile is not None and self.gold_timestamp_seconds is not None:
            actions.append(
                direct_action(
                    RawObservation(
                        timestamp_seconds=self.gold_timestamp_seconds,
                        actor="system",
                        kind=ObservationKind.GOLD,
                        tile=self.context.gold_tile,
                        confidence=1.0,
                        evidence_refs=self.evidence_refs,
                        details={
                            "source": "hand_context_assembler_v0_1",
                        },
                    )
                )
            )
        return tuple(sorted(actions, key=lambda item: item.timestamp_seconds))


def _dedupe_refs(groups: Iterable[Iterable[str]]) -> tuple[str, ...]:
    refs: list[str] = []
    for group in groups:
        for ref in group:
            value = str(ref)
            if value and value not in refs:
                refs.append(value)
    return tuple(refs)


def _seat_scores(
    public_state: PublicStateObservation,
    player_seat: int | None,
) -> tuple[int, int] | None:
    """Map UI score order (top-right, bottom-left) into seat order.

    Bottom-left is the local player UI position. We refuse to invent which seat
    that corresponds to unless the caller supplies player_seat.
    """
    if player_seat is None or public_state.score_pair is None:
        return None
    top_right, bottom_left = public_state.score_pair
    if player_seat == 0:
        return bottom_left, top_right
    return top_right, bottom_left


def _dealer_consensus(
    evidence: Iterable[DealerEvidence],
    *,
    minimum_votes: int,
    minimum_confidence: float,
) -> tuple[int | None, tuple[str, ...], tuple[str, ...], float | None]:
    rows = tuple(
        item
        for item in evidence
        if item.confidence >= minimum_confidence and item.dealer_seat is not None
    )
    if not rows:
        return None, ("dealer_unreadable",), (), None

    counts = Counter(item.dealer_seat for item in rows)
    seat, votes = counts.most_common(1)[0]
    winners = [candidate for candidate, count in counts.items() if count == votes]
    if votes < minimum_votes:
        return (
            None,
            ("dealer_consensus",),
            _dedupe_refs(item.evidence_refs for item in rows),
            None,
        )
    if len(winners) != 1:
        return (
            None,
            ("dealer_tie",),
            _dedupe_refs(item.evidence_refs for item in rows),
            None,
        )
    accepted = tuple(item for item in rows if item.dealer_seat == seat)
    return (
        int(seat),
        (),
        _dedupe_refs(item.evidence_refs for item in accepted),
        min(item.timestamp_seconds for item in accepted),
    )


def _gold_consensus(
    observations: Iterable[RawObservation],
    *,
    minimum_votes: int,
    minimum_confidence: float,
) -> tuple[str | None, tuple[str, ...], tuple[str, ...], float | None]:
    rows = tuple(
        item
        for item in observations
        if item.kind == ObservationKind.GOLD
        and item.tile
        and item.confidence >= minimum_confidence
    )
    if not rows:
        return None, ("gold_unreadable",), (), None

    counts = Counter(item.tile for item in rows)
    tile, votes = counts.most_common(1)[0]
    winners = [candidate for candidate, count in counts.items() if count == votes]
    refs = _dedupe_refs(item.evidence_refs for item in rows)
    if votes < minimum_votes:
        return None, ("gold_consensus",), refs, None
    if len(winners) != 1:
        return None, ("gold_tie",), refs, None

    accepted = tuple(item for item in rows if item.tile == tile)
    return (
        str(tile),
        (),
        _dedupe_refs(item.evidence_refs for item in accepted),
        min(item.timestamp_seconds for item in accepted),
    )


def assemble_hand_context(
    public_state: PublicStateObservation,
    *,
    player_seat: int | None,
    dealer_evidence: Iterable[DealerEvidence] = (),
    gold_observations: Iterable[RawObservation] = (),
    public_state_evidence_refs: Iterable[str] = (),
    public_state_timestamp_seconds: float | None = None,
    minimum_dealer_votes: int = 2,
    minimum_gold_votes: int = 2,
    minimum_confidence: float = 0.0,
    room_options: Iterable[str] = (),
) -> HandContextDraft:
    """Build a conservative HandContext without Mahjong-rule inference."""

    if player_seat is not None and (
        type(player_seat) is not int or player_seat not in (0, 1)
    ):
        raise ValueError("player_seat must be seat 0, seat 1 or None")
    if minimum_dealer_votes < 1 or minimum_gold_votes < 1:
        raise ValueError("minimum votes must be >= 1")
    if not 0 <= minimum_confidence <= 1:
        raise ValueError("minimum_confidence must be within [0, 1]")
    if public_state_timestamp_seconds is not None and (
        isinstance(public_state_timestamp_seconds, bool)
        or not isinstance(public_state_timestamp_seconds, (int, float))
        or public_state_timestamp_seconds < 0
    ):
        raise ValueError(
            "public_state_timestamp_seconds must be nonnegative numeric or None"
        )

    issues: list[str] = []
    if public_state.hand_number is None:
        issues.append("hand_index_unknown")
    if public_state.score_pair is None:
        issues.append("initial_scores_unknown")
    elif player_seat is None:
        issues.append("player_seat_unknown")

    initial_scores = _seat_scores(public_state, player_seat)

    dealer, dealer_issues, dealer_refs, dealer_ts = _dealer_consensus(
        dealer_evidence,
        minimum_votes=minimum_dealer_votes,
        minimum_confidence=minimum_confidence,
    )
    issues.extend(dealer_issues)

    gold_tile, gold_issues, gold_refs, gold_ts = _gold_consensus(
        gold_observations,
        minimum_votes=minimum_gold_votes,
        minimum_confidence=minimum_confidence,
    )
    issues.extend(gold_issues)

    for issue in public_state.issues:
        issues.append(f"public_state:{issue}")

    refs = _dedupe_refs(
        (
            tuple(str(ref) for ref in public_state_evidence_refs if str(ref)),
            dealer_refs,
            gold_refs,
        )
    )
    hand_start_ts = (
        float(public_state_timestamp_seconds)
        if public_state_timestamp_seconds is not None
        and public_state.hand_number is not None
        else None
    )
    if hand_start_ts is None:
        hand_start_ts = dealer_ts

    context = HandContext(
        player_seat=player_seat,
        dealer=dealer,
        initial_scores=initial_scores,
        current_dealer_base=None,
        gold_tile=gold_tile,
        room_options=tuple(str(value) for value in room_options if str(value)),
        notes=(
            "machine-assembled opening context; canonical timeline evidence remains UNKNOWN until review",
        ),
    )

    return HandContextDraft(
        hand_index=public_state.hand_number,
        context=context,
        issues=tuple(dict.fromkeys(issues)),
        evidence_refs=refs,
        hand_start_timestamp_seconds=hand_start_ts,
        gold_timestamp_seconds=gold_ts,
    )
