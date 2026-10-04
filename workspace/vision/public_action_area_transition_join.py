"""#69 fail-closed join between action-area onset and public-zone change.

This module deliberately stops before action reconstruction.  An action-area
animation can be a prompt, highlight or transition effect, while a later river
or meld change can have unrelated latency.  Correlation therefore produces a
review candidate only; it never emits ``RawObservation`` or a runtime action.

Source identifiers and exact frames are retained only in memory for lineage
checks.  The public serialization omits them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from workspace.vision.public_action_area_onset import ActionAreaOnsetCandidate

_SHA = re.compile(r"^[a-f0-9]{64}$")
_CHANNELS = frozenset(("river", "meld", "hand_count"))
_ACTORS = frozenset(("player", "opponent", "UNKNOWN"))


@dataclass(frozen=True)
class PublicTransitionFact:
    """Independently produced public-zone transition, not an action."""

    channel: str
    actor_hint: str
    first_stable_frame: int
    source_session: str
    source_sha256: str
    stream_epoch: int
    independently_verified: bool
    status: str = "PUBLIC_TRANSITION_CANDIDATE_ONLY"


@dataclass(frozen=True)
class ActionAreaTransitionJoin:
    status: str
    reason: str
    region_actor_hint: str = "UNKNOWN"
    transition_actor_hint: str = "UNKNOWN"
    joined_channels: tuple[str, ...] = ()
    onset_frame: int | None = None
    transition_frame: int | None = None
    transition_order: str | None = None
    source_session: str | None = None
    source_sha256: str | None = None
    stream_epoch: int | None = None

    def to_dict(self) -> dict:
        return {
            "schema_version": "public_action_area_transition_join_dev_v0_3",
            "development_only": True,
            "status": self.status,
            "reason": self.reason,
            "region_actor_hint": self.region_actor_hint,
            "transition_actor_hint": self.transition_actor_hint,
            "joined_channels": list(self.joined_channels),
            "transition_order": self.transition_order,
            "transition_offset_from_onset_frames": (
                self.transition_frame - self.onset_frame
                if self.transition_frame is not None
                and self.onset_frame is not None else None
            ),
            "tile_identity": "UNKNOWN",
            "actual_action_kind": "UNKNOWN",
            "actual_actor": "UNKNOWN",
            "raw_observation_emitted": False,
            "formal_accuracy_eligible": False,
            "safe_for_runtime": False,
            "safe_for_executor": False,
        }


def _unknown(reason: str) -> ActionAreaTransitionJoin:
    return ActionAreaTransitionJoin("UNKNOWN", reason)


def _valid_source(session, sha, epoch) -> bool:
    return (
        isinstance(session, str) and bool(session)
        and isinstance(sha, str) and bool(_SHA.fullmatch(sha))
        and type(epoch) is int and epoch >= 0
    )


def _valid_fact(fact: PublicTransitionFact) -> bool:
    return (
        isinstance(fact, PublicTransitionFact)
        and fact.channel in _CHANNELS
        and fact.actor_hint in _ACTORS
        and type(fact.first_stable_frame) is int
        and fact.first_stable_frame >= 0
        and _valid_source(
            fact.source_session, fact.source_sha256, fact.stream_epoch
        )
        and fact.independently_verified is True
        and fact.status == "PUBLIC_TRANSITION_CANDIDATE_ONLY"
    )


def join_action_area_to_public_transition(
    onset: ActionAreaOnsetCandidate,
    transitions: Sequence[PublicTransitionFact],
    *,
    max_followup_frames: int,
) -> ActionAreaTransitionJoin:
    """Correlate one onset with one later river/meld change, without semantics.

    A hand-count delta may corroborate the unique public-zone change but can
    never form a join by itself.  Multiple river/meld changes inside the window
    are ambiguous and fail closed rather than choosing the nearest one.
    """
    if (
        not isinstance(onset, ActionAreaOnsetCandidate)
        or onset.status != "ACTION_AREA_ONSET_CANDIDATE_ONLY"
        or onset.region_actor_hint not in ("player", "opponent")
        or type(onset.first_visible_frame) is not int
        or type(onset.confirmation_frame) is not int
        or onset.confirmation_frame < onset.first_visible_frame
        or not _valid_source(
            onset.source_session, onset.source_sha256, onset.stream_epoch
        )
    ):
        return _unknown("invalid_or_unverified_action_area_onset")
    if (
        type(max_followup_frames) is not int
        or max_followup_frames < 1
    ):
        return _unknown("invalid_transition_window")
    if not isinstance(transitions, Sequence) or isinstance(
        transitions, (str, bytes)
    ):
        return _unknown("invalid_transition_collection")
    if not transitions:
        return _unknown("no_independent_public_transition")
    if any(not _valid_fact(fact) for fact in transitions):
        return _unknown("invalid_or_unverified_public_transition")

    scope = (onset.source_session, onset.source_sha256, onset.stream_epoch)
    if any(
        (fact.source_session, fact.source_sha256, fact.stream_epoch) != scope
        for fact in transitions
    ):
        return _unknown("source_session_sha_or_epoch_changed")

    in_window = tuple(
        fact for fact in transitions
        if onset.confirmation_frame < fact.first_stable_frame
        and fact.first_stable_frame - onset.first_visible_frame
        <= max_followup_frames
    )
    if not in_window:
        return _unknown("no_public_transition_in_window")

    public_zone = tuple(
        fact for fact in in_window if fact.channel in ("river", "meld")
    )
    if not public_zone:
        return _unknown("hand_count_delta_alone_cannot_confirm_public_action")
    if len(public_zone) != 1:
        return _unknown("ambiguous_multiple_public_zone_transitions")

    anchor = public_zone[0]
    hand = tuple(fact for fact in in_window if fact.channel == "hand_count")
    if len(hand) > 1:
        return _unknown("ambiguous_multiple_hand_count_transitions")
    actor_hints = {
        fact.actor_hint for fact in in_window if fact.actor_hint != "UNKNOWN"
    }
    if len(actor_hints) > 1:
        return _unknown("conflicting_transition_actor_hints")

    channels = (anchor.channel,) + (("hand_count",) if hand else ())
    transition_actor = next(iter(actor_hints), "UNKNOWN")
    return ActionAreaTransitionJoin(
        "PUBLIC_TRANSITION_JOIN_CANDIDATE_ONLY",
        "source_locked_unique_nearby_public_zone_change_not_an_action",
        onset.region_actor_hint,
        transition_actor,
        channels,
        onset.first_visible_frame,
        anchor.first_stable_frame,
        "AFTER_ONSET",
        onset.source_session,
        onset.source_sha256,
        onset.stream_epoch,
    )
