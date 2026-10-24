"""Bridge trusted live opening facts into public match reconstruction.

This adapter is intentionally one-way and fail-closed.  It may emit a public
OPEN_GOLD fact only from a trusted final visible Gold.  It does not infer the
system's random selection from dice, wall position, RNG state, or any hidden
opening mechanic, and it never constructs a complete Environment GameState.
"""
from __future__ import annotations

from huian._legacy import env

from .live_opening_fact import LiveOpeningFact, LiveOpeningFactStatus
from .public_match_reconstruction import (
    ObservationKind,
    RawObservation,
    ReconstructedAction,
    direct_action,
)


_VISIBLE_GOLD_SOURCE = "VISIBLE_FINAL_GOLD_MULTIFRAME"


def gold_observation_from_live_opening_fact(
    fact: LiveOpeningFact,
) -> RawObservation | None:
    """Convert one trusted visible Gold fact into a public GOLD observation.

    ``confidence=1.0`` represents passage of the strict boolean trust contract,
    not a classifier probability.  The underlying classifier score is
    deliberately not invented here because ``LiveOpeningFact`` does not carry
    one.  Downstream consumers can audit this distinction through
    ``confidence_semantics`` in ``details``.
    """
    if not isinstance(fact, LiveOpeningFact):
        raise TypeError("fact must be a LiveOpeningFact")
    if fact.status is not LiveOpeningFactStatus.TRUSTED:
        return None
    if not fact.state_tracker_ready or not fact.gold_trusted:
        return None
    if fact.source_kind != _VISIBLE_GOLD_SOURCE:
        return None
    if fact.selection_inference_used:
        return None
    if fact.safe_for_environment_state or fact.safe_for_executor:
        return None
    if not fact.source_session or fact.stream_epoch < 0:
        return None
    if fact.gold_tile is None:
        return None
    if fact.gold_tile in env.FLOWERS or fact.gold_tile not in env.BASE_TILES:
        return None
    if fact.issues:
        return None

    return RawObservation(
        timestamp_seconds=fact.timestamp_seconds,
        actor="system",
        kind=ObservationKind.GOLD,
        confidence=1.0,
        tile=fact.gold_tile,
        evidence_refs=(),
        details={
            "source_kind": fact.source_kind,
            "source_session": fact.source_session,
            "stream_epoch": fact.stream_epoch,
            "selection_inference_used": False,
            "safe_for_environment_state": False,
            "safe_for_executor": False,
            "confidence_semantics": "trusted_gate_boolean_not_classifier_score",
        },
    )


def open_gold_action_from_live_opening_fact(
    fact: LiveOpeningFact,
) -> ReconstructedAction | None:
    """Reuse the existing public reconstruction mapping for trusted live Gold."""
    observation = gold_observation_from_live_opening_fact(fact)
    if observation is None:
        return None
    return direct_action(observation)
