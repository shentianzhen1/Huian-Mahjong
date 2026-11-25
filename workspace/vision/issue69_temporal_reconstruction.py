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
from workspace.vision.public_meld_observer_corroboration import SourceBoundObserverFact


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
    hand_facts: Sequence[SourceBoundObserverFact] | Iterable[SourceBoundObserverFact] = (),
    claim_window_seconds: float,
    assembly_delay_seconds: float,
) -> dict:
    public = tuple(public_candidates)
    hands = tuple(hand_deltas)
    facts = tuple(hand_facts)
    scope = _single_scope(public, hands, facts)
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
            if row.kind != "DISCARD":
                excluded_context.append({
                    "frame_index": row.frame_index,
                    "candidate_kind": row.kind,
                    "reason": "river_non_discard_context_never_discard_evidence",
                    "evidence_refs": list(row.evidence_refs),
                })
                continue
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
            legacy_tiles = tuple(row.tile.split(",")) if row.tile else ()
            if row.tiles and legacy_tiles and row.tiles != legacy_tiles:
                raise ValueError("structured and legacy meld identities conflict")
            candidates = row.tiles or legacy_tiles
            complete = bool(candidates) and all(
                tile not in (None, "UNKNOWN") for tile in candidates
            )
            tiles = tuple(candidates) if complete else ()
            meld_details = {
                "frame": row.frame_index,
                "source_session": row.source_session,
                "stream_epoch": row.stream_epoch,
                "tile_identity_complete": complete,
                "tile_candidates": list(candidates),
            }
            if row.meld_group_size is not None:
                meld_details["group_size"] = row.meld_group_size
            if row.previous_meld_group_size is not None:
                meld_details["previous_group_size"] = row.previous_meld_group_size
            if row.previous_meld:
                meld_details["previous_meld"] = list(row.previous_meld)
            observations.append(RawObservation(
                timestamp_seconds=row.timestamp_seconds,
                actor=row.actor_hint.lower(),
                kind=ObservationKind.MELD_DELTA,
                tiles=tiles,
                confidence=1.0,
                evidence_refs=row.evidence_refs,
                details=meld_details,
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

    for fact in facts:
        if fact.channel != "hand" or fact.observation.kind is not ObservationKind.HAND_DELTA:
            raise ValueError("hand_facts must contain only source-bound HAND_DELTA facts")
        if not (
            fact.original_frame_verified
            and fact.stable_source_observation
            and fact.independent_public_region_verified
        ):
            raise ValueError("hand fact must remain source-verified and stable")
        observations.append(fact.observation)

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
        "meld_upgrade_candidates": [{
            "timestamp_seconds": row.timestamp_seconds,
            "frame_index": row.frame_index,
            "actor": row.actor_hint.lower(),
            "previous_group_size": row.previous_meld_group_size,
            "current_group_size": row.meld_group_size,
            "previous_meld": list(row.previous_meld),
            "current_tiles": list(row.tiles),
            "tile_identity_complete": bool(row.tiles) and all(
                tile not in (None, "UNKNOWN") for tile in row.tiles
            ),
            "action_kind": "UNKNOWN",
            "formal_promotion_evidence": False,
            "safe_for_runtime": False,
            "safe_for_executor": False,
        } for row in public if (
            row.channel == "meld"
            and row.previous_meld_group_size == 3
            and row.meld_group_size == 4
        )],
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


def _single_scope(public, hands, facts=()):
    scopes = {
        (row.source_session, row.source_sha256, row.stream_epoch)
        for row in public
    } | {
        (row.source_session, row.source_sha256, row.stream_epoch)
        for row in hands
    } | {
        (row.source_session, row.source_sha256, row.stream_epoch)
        for row in facts
    }
    if len(scopes) > 1:
        raise ValueError("all reconstruction inputs must share exact source scope")
    return next(iter(scopes), None)
