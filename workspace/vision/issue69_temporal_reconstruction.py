"""Bridge #69 source-scoped public candidates into TemporalActionAssembler.

Action-area onset is context-only and is deliberately never converted into a
RawObservation. Missing hand evidence therefore stays UNKNOWN rather than being
filled from UI prompts or Mahjong legality.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from workspace.vision.action_assembler import AssemblyConfig, TemporalActionAssembler
from workspace.vision.issue69_public_replay_orchestrator import PublicReplayCandidate
from workspace.vision.public_match_reconstruction import ObservationKind, RawObservation


@dataclass(frozen=True)
class HandDeltaCandidate:
    timestamp_seconds: float
    frame_index: int
    actor: str
    source_session: str
    source_sha256: str
    stream_epoch: int
    evidence_refs: tuple[str, ...]
    removed_tiles: tuple[str, ...] = ()
    removed_count: int | None = None
    confidence: float = 1.0


def reconstruct_public_candidates(
    public_candidates: Sequence[PublicReplayCandidate] | Iterable[PublicReplayCandidate],
    *,
    hand_deltas: Sequence[HandDeltaCandidate] | Iterable[HandDeltaCandidate] = (),
    claim_window_seconds: float,
    assembly_delay_seconds: float,
) -> dict:
    public = tuple(public_candidates)
    hands = tuple(hand_deltas)
    scope = _single_scope(public, hands)
    observations = []
    excluded_context = []

    for row in public:
        if row.channel == "action_area":
            excluded_context.append({
                "frame_index": row.frame_index,
                "reason": "action_area_context_never_action_evidence",
            })
            continue
        if row.channel == "river":
            observations.append(RawObservation(
                timestamp_seconds=row.timestamp_seconds,
                actor=row.actor_hint.lower(),
                kind=ObservationKind.DISCARD,
                tile=row.tile,
                confidence=1.0,
                evidence_refs=row.evidence_refs,
                details={
                    "frame": row.frame_index,
                    "source_session": row.source_session,
                    "stream_epoch": row.stream_epoch,
                },
            ))
            continue
        if row.channel == "meld":
            tiles = tuple(row.tile.split(",")) if row.tile else ()
            observations.append(RawObservation(
                timestamp_seconds=row.timestamp_seconds,
                actor=row.actor_hint.lower(),
                kind=ObservationKind.MELD_DELTA,
                tiles=tiles,
                confidence=1.0,
                evidence_refs=row.evidence_refs,
                details={
                    "frame": row.frame_index,
                    "source_session": row.source_session,
                    "stream_epoch": row.stream_epoch,
                    "tile_identity_complete": bool(tiles),
                },
            ))

    for hand in hands:
        details = {
            "frame": hand.frame_index,
            "source_session": hand.source_session,
            "stream_epoch": hand.stream_epoch,
        }
        if hand.removed_tiles:
            details["removed_tiles"] = list(hand.removed_tiles)
        elif hand.removed_count is not None:
            details["removed_count"] = hand.removed_count
        observations.append(RawObservation(
            timestamp_seconds=hand.timestamp_seconds,
            actor=hand.actor,
            kind=ObservationKind.HAND_DELTA,
            confidence=hand.confidence,
            evidence_refs=hand.evidence_refs,
            details=details,
        ))

    observations.sort(key=lambda item: (
        item.timestamp_seconds,
        int(item.details.get("frame", 0)),
        item.kind.value,
    ))
    assembler = TemporalActionAssembler(AssemblyConfig(
        claim_window_seconds=claim_window_seconds,
        assembly_delay_seconds=assembly_delay_seconds,
    ))
    actions = list(assembler.ingest_many(observations))
    actions.extend(assembler.flush())
    return {
        "schema_version": "issue69_temporal_reconstruction_v0_1",
        "source_session": scope[0] if scope else None,
        "input_observation_count": len(observations),
        "excluded_context": excluded_context,
        "actions": [{
            "timestamp_seconds": action.timestamp_seconds,
            "actor": action.actor,
            "kind": action.kind.value,
            "evidence_grade": action.evidence_grade.value,
            "tile": action.tile,
            "claimed_tile": action.claimed_tile,
            "meld": list(action.meld),
            "unknown_reasons": list(action.unknown_reasons),
            "evidence_refs": list(action.evidence_refs),
        } for action in actions],
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def _single_scope(public, hands):
    scopes = {
        (row.source_session, row.source_sha256, row.stream_epoch)
        for row in public
    } | {
        (row.source_session, row.source_sha256, row.stream_epoch)
        for row in hands
    }
    if len(scopes) > 1:
        raise ValueError("all reconstruction inputs must share exact source scope")
    return next(iter(scopes), None)
