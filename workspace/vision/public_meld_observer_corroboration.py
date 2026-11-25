"""Issue #69: DEVELOPMENT-ONLY reconciliation with independent observer output.

A human-reviewed discard/new-meld/delayed-shade correspondence is NOT an
automatically reconstructed action. This gate asks whether independently
produced river, hand-delta and meld-delta observations agree, in the SAME
original video, epoch, source region and bounded reviewed frame window.

It neither loads private footage nor modifies Runtime/Ledger/Rules/AI/Executor.
All successful outcomes remain owner-review candidates, NOT ground truth.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
from typing import Sequence

from workspace.vision.public_match_reconstruction import (
    EvidenceGrade, ObservationKind, PublicActionKind, RawObservation,
    reconstruct_claimed_meld,
)
from workspace.vision.public_meld_action_cross_evidence import (
    ManuallyReviewedNewMeld, ManuallyReviewedPublicDiscard,
    cross_check_reviewed_meld_event,
)
from workspace.vision.public_meld_delayed_shade_review import SourceScopedShadeFrame
from workspace.vision.public_meld_adjacent_onset import AdjacentMeldOnsetReview

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_CHANNEL_KIND = {
    "river": ObservationKind.DISCARD,
    "hand": ObservationKind.HAND_DELTA,
    "meld": ObservationKind.MELD_DELTA,
}
_CANDIDATE_TO_ACTION = {
    "CHI_LIKE": PublicActionKind.CHI,
    "PENG_LIKE": PublicActionKind.PENG,
    "KONG_LIKE": PublicActionKind.MING_GANG,
}


@dataclass(frozen=True)
class SourceBoundObserverFact:
    """Output from ONE separate automatic observation channel, not a label.

    These attestations must be produced by the actual source-pixel observer
    runner, never copied from the manual review. The audit itself cannot
    verify external video bytes; that responsibility remains with the runner.
    """
    channel: str
    observation: RawObservation
    source_session: str
    source_sha256: str
    stream_epoch: int
    frame_index: int
    original_frame_verified: bool
    stable_source_observation: bool
    independent_public_region_verified: bool


@dataclass(frozen=True)
class ObserverCorroborationAudit:
    status: str
    candidate_action_kind: str
    candidate_incoming_tile: str | None
    observer_evidence_grade: str
    reviewed_discard_frame: int | None
    reviewed_meld_frame: int | None
    observation_frames: tuple[int, ...]
    issues: tuple[str, ...]

    def to_dict(self) -> dict:
        # Do NOT serialize private original video SHA, local filenames or
        # direct-source metadata into a public GitHub evidence note.
        return {
            "schema_version": "public_meld_observer_corroboration_dev_v0_1",
            "development_only": True,
            "status": self.status,
            "candidate_action_kind": self.candidate_action_kind,
            "candidate_incoming_tile": self.candidate_incoming_tile,
            "observer_evidence_grade": self.observer_evidence_grade,
            "reviewed_window_frames": (
                [self.reviewed_discard_frame, self.reviewed_meld_frame]
                if self.reviewed_discard_frame is not None
                and self.reviewed_meld_frame is not None else None
            ),
            "independent_observation_frames": list(self.observation_frames),
            "requires_source_byte_verification_by_caller": True,
            "requires_owner_event_truth_review": True,
            "owner_confirmed_event_truth": False,
            "source_disjoint_blind_test": False,
            "production_action_kind": "UNKNOWN",
            "production_incoming_tile_id": "UNKNOWN",
            "actor": "UNKNOWN",
            "turn_actor": "UNKNOWN",
            "formal_promotion_evidence": False,
            "safe_for_runtime": False,
            "safe_for_executor": False,
            "issues": list(self.issues),
        }


def _stop(reason: str, *, conflict: bool = False) -> ObserverCorroborationAudit:
    return ObserverCorroborationAudit(
        "CONFLICT" if conflict else "UNKNOWN",
        "UNKNOWN", None, "UNKNOWN", None, None, (), (reason,),
    )


def corroborate_with_independent_observers(
    reviewed_discard: ManuallyReviewedPublicDiscard,
    reviewed_meld: ManuallyReviewedNewMeld,
    shade_frames: Sequence[SourceScopedShadeFrame],
    river_fact: SourceBoundObserverFact,
    hand_fact: SourceBoundObserverFact,
    meld_fact: SourceBoundObserverFact,
    *,
    verified_screen_side_actors: dict[str, str] | None = None,
    reviewed_last_frame: int | None = None,
    verified_adjacent_meld_onset: AdjacentMeldOnsetReview | None = None,
) -> ObserverCorroborationAudit:
    """Compare two disjoint evidence streams without promoting an action.

    The human review fixes the expected discard/face identities. The three
    independent automatic observations MUST come from different channels,
    with nonoverlapping evidence_refs, matching private source provenance and
    the reviewed temporal window. SHA, exact source frame and region flags
    are caller attestations, not secretly verified by this pure function.

    CHI still needs the later stable positional shade to establish which
    suited face was claimed. Identical PENG/MING_GANG do NOT require shade.
    ADD_KONG is excluded: that requires an independently seen existing PENG.
    A hand crop, a pre-existing meld receiving delayed shade, or a single
    unbracketed late screenshot is not independent evidence of a NEW meld.
    The adjacent onset proof is a separate *source-verified public-region*
    frame pair, not a hand-shadow inference.
    """
    candidate = cross_check_reviewed_meld_event(
        reviewed_discard, reviewed_meld, shade_frames,
    )
    if (
        candidate.status != "DEVELOPMENT_CORROBORATED_CANDIDATE"
        or candidate.candidate_action_kind not in _CANDIDATE_TO_ACTION
        or candidate.reviewed_incoming_tile_candidate is None
    ):
        return _stop("manual_development_correspondence_not_source_qualified")

    # A Boolean "group was absent" on a late review sheet cannot establish
    # source-visible onset. Require separate verified, adjacent original
    # before/after public-MELD ROI observations, not hand brightness.
    onset = verified_adjacent_meld_onset
    if (
        not isinstance(onset, AdjacentMeldOnsetReview)
        or onset.status != "NEW_MELD_VISUALLY_BRACKETED_OWNER_ACTION_PENDING"
        or onset.source_session != reviewed_meld.source_session
        or onset.source_sha256 != reviewed_meld.source_sha256
        or onset.stream_epoch != reviewed_meld.stream_epoch
        or onset.screen_side != reviewed_meld.screen_side
        or onset.target_track_id != reviewed_meld.meld_track_id
        or onset.target_face_ids != reviewed_meld.face_ids_left_to_right
        or type(onset.prior_frame) is not int
        or type(onset.first_visible_frame) is not int
        or onset.first_visible_frame != onset.prior_frame + 1
        or onset.prior_frame < reviewed_discard.frame_index
        or onset.first_visible_frame > reviewed_meld.frame_index
    ):
        return _stop("adjacent_original_frame_public_meld_onset_missing_or_inconsistent")

    if not isinstance(verified_screen_side_actors, dict) or (
        set(verified_screen_side_actors) != {"upper", "lower"}
        or set(verified_screen_side_actors.values()) != {"player", "opponent"}
    ):
        return _stop("independent_screen_side_actor_mapping_missing")

    if (
        not _SHA256.fullmatch(reviewed_discard.source_sha256)
        or not reviewed_discard.source_session
        or not reviewed_meld.meld_track_id
        or type(reviewed_discard.stream_epoch) is not int
        or reviewed_discard.stream_epoch < 0
    ):
        return _stop("invalid_reviewed_source_scope")

    expected_scope = (
        reviewed_discard.source_session,
        reviewed_discard.source_sha256,
        reviewed_discard.stream_epoch,
    )
    facts = (river_fact, hand_fact, meld_fact)
    for expected_channel, fact in zip(("river", "hand", "meld"), facts):
        if fact.channel != expected_channel or fact.observation.kind != (
            _CHANNEL_KIND[expected_channel]
        ):
            return _stop("observer_channel_or_observation_kind_mismatch")
        if (
            (fact.source_session, fact.source_sha256, fact.stream_epoch)
            != expected_scope
        ):
            return _stop("observer_source_session_sha_or_epoch_mismatch", conflict=True)
        if (
            type(fact.frame_index) is not int or fact.frame_index < 0
            or fact.original_frame_verified is not True
            or fact.stable_source_observation is not True
            or fact.independent_public_region_verified is not True
        ):
            return _stop("unverified_source_frame_or_region_observation")

    # Duplicate evidence from the same pixel/label cannot masquerade as
    # independent river/hand/meld observer support.
    ref_sets = [set(f.observation.evidence_refs) for f in facts]
    if (
        any(not refs for refs in ref_sets)
        or ref_sets[0] & ref_sets[1]
        or ref_sets[0] & ref_sets[2]
        or ref_sets[1] & ref_sets[2]
    ):
        return _stop("observer_channels_share_or_lack_provenance")

    if (
        river_fact.observation.actor != verified_screen_side_actors[
            reviewed_discard.screen_side
        ]
        or hand_fact.observation.actor != verified_screen_side_actors[
            reviewed_meld.screen_side
        ]
        or meld_fact.observation.actor != hand_fact.observation.actor
    ):
        return _stop("independent_actor_vs_screen_side_conflict", conflict=True)

    if (
        type(reviewed_last_frame) is not int
        or reviewed_last_frame < reviewed_meld.frame_index
    ):
        # The caller must explicitly bound its independent source review.
        # There is deliberately no guessed global animation timeout.
        return _stop("explicit_source_review_window_missing")

    obs_frames = tuple(f.frame_index for f in facts)
    if (
        not (
            reviewed_discard.frame_index <= obs_frames[0]
            <= reviewed_meld.frame_index
        )
        or not all(
            reviewed_discard.frame_index <= n <= reviewed_last_frame
            for n in obs_frames
        )
        or obs_frames[0] > obs_frames[1]
        or obs_frames[0] > obs_frames[2]
        or obs_frames[2] < reviewed_meld.frame_index
    ):
        return _stop("observer_events_outside_reviewed_temporal_window")

    obs_times = tuple(f.observation.timestamp_seconds for f in facts)
    if obs_times[0] > obs_times[1] or obs_times[0] > obs_times[2]:
        return _stop("observer_timestamp_precedes_claimed_discard")

    result = reconstruct_claimed_meld(
        river_fact.observation,
        hand_fact.observation,
        meld_fact.observation,
    )
    if result.evidence_grade != EvidenceGrade.CORROBORATED:
        return _stop(
            "independent_observer_action_incomplete_or_conflicting",
            conflict=result.kind == PublicActionKind.EVIDENCE_CONFLICT,
        )
    if (
        result.kind != _CANDIDATE_TO_ACTION[candidate.candidate_action_kind]
        or result.claimed_tile != candidate.reviewed_incoming_tile_candidate
        or Counter(result.meld) != Counter(reviewed_meld.face_ids_left_to_right)
    ):
        return _stop("independent_observer_vs_manual_event_conflict", conflict=True)

    # The existing reconstruction permits a hand-count-only claim. Accept
    # that evidence only as a reviewable consistency check, not tile truth.
    return ObserverCorroborationAudit(
        status="OBSERVER_CORROBORATED_OWNER_REVIEW_PENDING",
        candidate_action_kind=candidate.candidate_action_kind,
        candidate_incoming_tile=candidate.reviewed_incoming_tile_candidate,
        observer_evidence_grade=result.evidence_grade.value,
        reviewed_discard_frame=reviewed_discard.frame_index,
        reviewed_meld_frame=reviewed_meld.frame_index,
        observation_frames=obs_frames,
        issues=(
            "reviewed_source_observations_not_owner_approved_event_truth",
            "same_existing_matches_development_only_not_blind_promotion",
        ),
    )
