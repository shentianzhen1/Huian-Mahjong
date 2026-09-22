"""Read-only public match reconstruction contracts for Vision.

This module turns already-observed public UI facts into auditable public actions.
It deliberately does not mutate Rules, Environment, AI, Hint Alpha, or Executor
state. Missing or contradictory evidence fails closed to UNKNOWN/conflict.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from huian.evidence.timeline import TimelineEvent


ACTORS = frozenset({"player", "opponent", "system", "unknown"})
YOUJIN_STATES = frozenset({"NORMAL", "YOUJIN", "DOUBLE_YOU", "TRIPLE_YOU", "UNKNOWN"})


class EvidenceGrade(str, Enum):
    DIRECT = "DIRECT"
    CORROBORATED = "CORROBORATED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class ObservationKind(str, Enum):
    HAND_START = "HAND_START"
    GOLD = "GOLD"
    DISCARD = "DISCARD"
    HAND_DELTA = "HAND_DELTA"
    MELD_DELTA = "MELD_DELTA"
    YOUJIN_STATE = "YOUJIN_STATE"
    HU = "HU"
    SETTLEMENT = "SETTLEMENT"


class PublicActionKind(str, Enum):
    HAND_START = "HAND_START"
    OPEN_GOLD = "OPEN_GOLD"
    DISCARD = "DISCARD"
    CHI = "CHI"
    PENG = "PENG"
    MING_GANG = "MING_GANG"
    ADD_KONG = "ADD_KONG"
    HU = "HU"
    YOUJIN_STATE = "YOUJIN_STATE"
    SETTLEMENT = "SETTLEMENT"
    UNKNOWN_ACTION = "UNKNOWN_ACTION"
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"


def _tuple_of_strings(value: Any, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        raise ValueError(f"{name} must be a sequence, not a string")
    result = tuple(str(item) for item in value)
    if any(not item for item in result):
        raise ValueError(f"{name} contains an empty value")
    return result


def _kind(value: ObservationKind | str) -> ObservationKind:
    if isinstance(value, ObservationKind):
        return value
    return ObservationKind(value)


@dataclass(frozen=True)
class RawObservation:
    """One source observation before Mahjong-action reconstruction.

    Convention:
    - DISCARD: tile is the public discarded tile.
    - HAND_DELTA: details contains removed_tiles / added_tiles.
    - MELD_DELTA: tiles is one newly visible exposed meld.
    - YOUJIN_STATE: details["state"] is an observed state label.
    """

    timestamp_seconds: float
    actor: str
    kind: ObservationKind | str
    confidence: float = 1.0
    tile: str | None = None
    tiles: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.timestamp_seconds, bool) or not isinstance(
            self.timestamp_seconds, (int, float)
        ):
            raise ValueError("timestamp_seconds must be numeric")
        if self.timestamp_seconds < 0:
            raise ValueError("timestamp_seconds must be nonnegative")
        if self.actor not in ACTORS:
            raise ValueError(f"unsupported actor: {self.actor}")
        if isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)):
            raise ValueError("confidence must be numeric")
        if not 0 <= float(self.confidence) <= 1:
            raise ValueError("confidence must be between 0 and 1")
        object.__setattr__(self, "timestamp_seconds", float(self.timestamp_seconds))
        object.__setattr__(self, "kind", _kind(self.kind))
        object.__setattr__(self, "confidence", float(self.confidence))
        object.__setattr__(self, "tiles", _tuple_of_strings(self.tiles, "tiles"))
        object.__setattr__(
            self, "evidence_refs", _tuple_of_strings(self.evidence_refs, "evidence_refs")
        )
        if not isinstance(self.details, dict):
            raise ValueError("details must be a dictionary")
        object.__setattr__(self, "details", dict(self.details))


@dataclass(frozen=True)
class ReconstructedAction:
    timestamp_seconds: float
    actor: str
    kind: PublicActionKind
    evidence_grade: EvidenceGrade
    confidence: float
    tile: str | None = None
    meld: tuple[str, ...] = ()
    claimed_tile: str | None = None
    consumed_from_hand: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    unknown_reasons: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.actor not in ACTORS:
            raise ValueError(f"unsupported actor: {self.actor}")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        object.__setattr__(self, "meld", _tuple_of_strings(self.meld, "meld"))
        object.__setattr__(
            self,
            "consumed_from_hand",
            _tuple_of_strings(self.consumed_from_hand, "consumed_from_hand"),
        )
        object.__setattr__(
            self, "evidence_refs", _tuple_of_strings(self.evidence_refs, "evidence_refs")
        )
        object.__setattr__(
            self, "unknown_reasons", _tuple_of_strings(self.unknown_reasons, "unknown_reasons")
        )
        object.__setattr__(self, "details", dict(self.details))

    def to_timeline_event(self) -> TimelineEvent:
        evidence_level = {
            EvidenceGrade.DIRECT: "direct_observation",
            EvidenceGrade.CORROBORATED: "derived_from_confirmed",
            EvidenceGrade.INFERRED: "derived_from_confirmed",
            EvidenceGrade.UNKNOWN: "unknown",
        }[self.evidence_grade]
        details = {
            **self.details,
            "reconstruction_evidence_grade": self.evidence_grade.value,
            "reconstruction_confidence": round(self.confidence, 6),
        }
        if self.claimed_tile is not None:
            details["claimed_tile"] = self.claimed_tile
        if self.meld:
            details["meld"] = list(self.meld)
        if self.consumed_from_hand:
            details["consumed_from_hand"] = list(self.consumed_from_hand)
        if self.unknown_reasons:
            details["reconstruction_unknown_reasons"] = list(self.unknown_reasons)
        return TimelineEvent(
            timestamp_seconds=self.timestamp_seconds,
            actor=self.actor,
            kind=self.kind.value,
            evidence_level=evidence_level,
            tile=self.tile or self.claimed_tile,
            state_interpretation=self.details.get("state_interpretation"),
            result=self.details.get("result"),
            evidence_refs=self.evidence_refs,
            details=details,
        )


def _refs(*observations: RawObservation) -> tuple[str, ...]:
    result: list[str] = []
    for observation in observations:
        for ref in observation.evidence_refs:
            if ref not in result:
                result.append(ref)
    return tuple(result)


def _unknown(
    *,
    timestamp_seconds: float,
    actor: str,
    reason: str,
    observations: tuple[RawObservation, ...],
    conflict: bool = False,
) -> ReconstructedAction:
    return ReconstructedAction(
        timestamp_seconds=timestamp_seconds,
        actor=actor,
        kind=(
            PublicActionKind.EVIDENCE_CONFLICT
            if conflict
            else PublicActionKind.UNKNOWN_ACTION
        ),
        evidence_grade=EvidenceGrade.UNKNOWN,
        confidence=min((item.confidence for item in observations), default=0.0),
        evidence_refs=_refs(*observations),
        unknown_reasons=(reason,),
    )


def _removed_tiles(observation: RawObservation) -> tuple[str, ...]:
    return _tuple_of_strings(observation.details.get("removed_tiles", ()), "removed_tiles")


def _same_tile_group(tiles: tuple[str, ...]) -> bool:
    return bool(tiles) and len(set(tiles)) == 1


def _suited_sequence(tiles: tuple[str, ...]) -> bool:
    if len(tiles) != 3:
        return False
    parsed: list[tuple[str, int]] = []
    for tile in tiles:
        if len(tile) != 2 or tile[0] not in {"M", "P", "S"} or not tile[1].isdigit():
            return False
        rank = int(tile[1])
        if not 1 <= rank <= 9:
            return False
        parsed.append((tile[0], rank))
    suits = {suit for suit, _ in parsed}
    ranks = sorted(rank for _, rank in parsed)
    return len(suits) == 1 and ranks[1] == ranks[0] + 1 and ranks[2] == ranks[1] + 1


def reconstruct_claimed_meld(
    discard: RawObservation,
    hand_delta: RawObservation,
    meld_delta: RawObservation,
) -> ReconstructedAction:
    """Reconstruct CHI/PENG/MING_GANG from three public observations."""

    observations = (discard, hand_delta, meld_delta)
    timestamp = max(item.timestamp_seconds for item in observations)
    actor = meld_delta.actor

    if discard.kind != ObservationKind.DISCARD:
        return _unknown(
            timestamp_seconds=timestamp,
            actor=actor,
            reason="missing_discard_observation",
            observations=observations,
        )
    if hand_delta.kind != ObservationKind.HAND_DELTA:
        return _unknown(
            timestamp_seconds=timestamp,
            actor=actor,
            reason="missing_hand_delta_observation",
            observations=observations,
        )
    if meld_delta.kind != ObservationKind.MELD_DELTA:
        return _unknown(
            timestamp_seconds=timestamp,
            actor=actor,
            reason="missing_meld_delta_observation",
            observations=observations,
        )
    if actor not in {"player", "opponent"} or hand_delta.actor != actor:
        return _unknown(
            timestamp_seconds=timestamp,
            actor=actor,
            reason="meld_and_hand_actor_mismatch",
            observations=observations,
            conflict=True,
        )
    if discard.actor == actor or discard.actor not in {"player", "opponent"}:
        return _unknown(
            timestamp_seconds=timestamp,
            actor=actor,
            reason="claimed_discard_actor_mismatch",
            observations=observations,
            conflict=True,
        )
    if not discard.tile:
        return _unknown(
            timestamp_seconds=timestamp,
            actor=actor,
            reason="discard_tile_unknown",
            observations=observations,
        )

    meld = meld_delta.tiles
    removed = _removed_tiles(hand_delta)
    if not meld:
        return _unknown(
            timestamp_seconds=timestamp,
            actor=actor,
            reason="new_meld_tiles_unknown",
            observations=observations,
        )
    if not removed:
        return _unknown(
            timestamp_seconds=timestamp,
            actor=actor,
            reason="consumed_hand_tiles_unknown",
            observations=observations,
        )

    expected = Counter(meld)
    if expected[discard.tile] < 1:
        return _unknown(
            timestamp_seconds=timestamp,
            actor=actor,
            reason="claimed_tile_missing_from_new_meld",
            observations=observations,
            conflict=True,
        )
    expected[discard.tile] -= 1
    if expected[discard.tile] == 0:
        del expected[discard.tile]
    if Counter(removed) != expected:
        return _unknown(
            timestamp_seconds=timestamp,
            actor=actor,
            reason="hand_delta_does_not_match_claimed_meld",
            observations=observations,
            conflict=True,
        )

    kind: PublicActionKind | None = None
    if len(meld) == 3 and _same_tile_group(meld):
        kind = PublicActionKind.PENG
    elif len(meld) == 3 and _suited_sequence(meld):
        kind = PublicActionKind.CHI
    elif len(meld) == 4 and _same_tile_group(meld):
        kind = PublicActionKind.MING_GANG

    if kind is None:
        return _unknown(
            timestamp_seconds=timestamp,
            actor=actor,
            reason="meld_shape_not_classifiable",
            observations=observations,
        )

    return ReconstructedAction(
        timestamp_seconds=timestamp,
        actor=actor,
        kind=kind,
        evidence_grade=EvidenceGrade.CORROBORATED,
        confidence=min(item.confidence for item in observations),
        claimed_tile=discard.tile,
        meld=meld,
        consumed_from_hand=removed,
        evidence_refs=_refs(*observations),
        details={
            "source_discard_actor": discard.actor,
            "evidence_components": ["discard", "hand_delta", "meld_delta"],
        },
    )


def reconstruct_add_kong(
    hand_delta: RawObservation,
    meld_delta: RawObservation,
) -> ReconstructedAction:
    """Recognize a Peng-to-four-tile exposed meld transition.

    The previous exposed meld must be explicitly supplied by the meld observer
    in details["previous_meld"]. Without it, AN_GANG vs ADD_KONG stays UNKNOWN.
    """

    observations = (hand_delta, meld_delta)
    timestamp = max(item.timestamp_seconds for item in observations)
    actor = meld_delta.actor
    if (
        hand_delta.kind != ObservationKind.HAND_DELTA
        or meld_delta.kind != ObservationKind.MELD_DELTA
    ):
        return _unknown(
            timestamp_seconds=timestamp,
            actor=actor,
            reason="missing_kong_transition_observation",
            observations=observations,
        )
    if hand_delta.actor != actor or actor not in {"player", "opponent"}:
        return _unknown(
            timestamp_seconds=timestamp,
            actor=actor,
            reason="kong_transition_actor_mismatch",
            observations=observations,
            conflict=True,
        )

    previous = _tuple_of_strings(meld_delta.details.get("previous_meld", ()), "previous_meld")
    current = meld_delta.tiles
    removed = _removed_tiles(hand_delta)
    if not (
        len(previous) == 3
        and _same_tile_group(previous)
        and len(current) == 4
        and _same_tile_group(current)
        and previous[0] == current[0]
        and removed == (current[0],)
    ):
        return _unknown(
            timestamp_seconds=timestamp,
            actor=actor,
            reason="not_a_confirmed_peng_to_add_kong_transition",
            observations=observations,
        )

    return ReconstructedAction(
        timestamp_seconds=timestamp,
        actor=actor,
        kind=PublicActionKind.ADD_KONG,
        evidence_grade=EvidenceGrade.CORROBORATED,
        confidence=min(item.confidence for item in observations),
        tile=current[0],
        meld=current,
        consumed_from_hand=removed,
        evidence_refs=_refs(*observations),
        details={
            "previous_meld": list(previous),
            "evidence_components": ["hand_delta", "meld_delta"],
        },
    )


def direct_action(observation: RawObservation) -> ReconstructedAction:
    """Convert public facts that do not require cross-observation reconstruction."""

    mapping = {
        ObservationKind.HAND_START: PublicActionKind.HAND_START,
        ObservationKind.GOLD: PublicActionKind.OPEN_GOLD,
        ObservationKind.DISCARD: PublicActionKind.DISCARD,
        ObservationKind.YOUJIN_STATE: PublicActionKind.YOUJIN_STATE,
        ObservationKind.HU: PublicActionKind.HU,
        ObservationKind.SETTLEMENT: PublicActionKind.SETTLEMENT,
    }
    kind = mapping.get(observation.kind)
    if kind is None:
        return _unknown(
            timestamp_seconds=observation.timestamp_seconds,
            actor=observation.actor,
            reason="observation_requires_reconstruction",
            observations=(observation,),
        )

    unknown_reasons: tuple[str, ...] = ()
    grade = EvidenceGrade.DIRECT

    if observation.kind == ObservationKind.GOLD and not observation.tile:
        grade = EvidenceGrade.UNKNOWN
        unknown_reasons = ("gold_tile_unknown",)
    elif observation.kind == ObservationKind.DISCARD and not observation.tile:
        grade = EvidenceGrade.UNKNOWN
        unknown_reasons = ("discard_tile_unknown",)
    elif observation.kind == ObservationKind.YOUJIN_STATE:
        state = observation.details.get("state", "UNKNOWN")
        if state not in YOUJIN_STATES:
            raise ValueError(f"unsupported Youjin state: {state}")
        if state == "UNKNOWN":
            grade = EvidenceGrade.UNKNOWN
            unknown_reasons = ("youjin_state_unknown",)
    elif observation.kind == ObservationKind.HU and not observation.details.get("subtype"):
        grade = EvidenceGrade.UNKNOWN
        unknown_reasons = ("hu_subtype_unconfirmed",)

    return ReconstructedAction(
        timestamp_seconds=observation.timestamp_seconds,
        actor=observation.actor,
        kind=kind,
        evidence_grade=grade,
        confidence=observation.confidence,
        tile=observation.tile,
        evidence_refs=observation.evidence_refs,
        unknown_reasons=unknown_reasons,
        details=observation.details,
    )
