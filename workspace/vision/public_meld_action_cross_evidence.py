"""Issue #69: strict DEVELOPMENT-ONLY cross-evidence for delayed meld shading.

Independent preceding visible discard -> first reviewed public meld. For CHI-like
sequences, a same-track LATER SHADE may identify/confirm the claimed slot. For
PENG/KONG-like identical-tile groups, owner observation confirms there is no
useful positional shade: all tiles are identical, so shade is neither required
nor expected. The face-wide shadow appears AFTER a CHI action and MUST NOT be
used as the action time. A successful result is an assistant-reviewed candidate
for a future owner audit, never a runtime action or blind accuracy.

The caller must verify original video hashes and independently inspect the
discard and missing->new meld transition; this pure gate does not look at pixels.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Sequence

from workspace.vision.public_meld_delayed_shade_review import (
    DelayedShadeReview, SourceScopedShadeFrame, review_delayed_shade,
)

_SHA = re.compile(r"^[a-f0-9]{64}$")
_NUMERIC = re.compile(r"^[MPS][1-9]$")
_HONORS = frozenset(("E", "S", "W", "N", "R", "G", "B"))


@dataclass(frozen=True)
class ManuallyReviewedPublicDiscard:
    source_session: str
    source_sha256: str
    stream_epoch: int
    frame_index: int
    screen_side: str
    visible_tile_id: str
    original_video_sha_verified: bool
    source_frame_pixel_verified: bool
    explicit_tile_manually_reviewed: bool
    no_intervening_public_action_reviewed: bool


@dataclass(frozen=True)
class ManuallyReviewedNewMeld:
    source_session: str
    source_sha256: str
    stream_epoch: int
    meld_track_id: str
    frame_index: int
    screen_side: str
    face_ids_left_to_right: tuple[str, ...]
    original_video_sha_verified: bool
    source_frame_pixel_verified: bool
    user_approved_face_id_provenance: bool
    independently_reviewed_absent_before_present: bool


@dataclass(frozen=True)
class DevelopmentMeldEventCandidate:
    status: str
    candidate_action_kind: str
    reviewed_incoming_tile_candidate: str | None
    shaded_face_index: int | None
    preceding_discard_frame: int | None
    first_stable_meld_frame: int | None
    shade_first_stable_frame: int | None
    appearance_delay_frames: int | None
    issues: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "schema_version": "public_meld_discard_delayed_shade_development_v0_1",
            "development_only": True,
            "owner_confirmed_event_truth": False,
            "independent_blind_test": False,
            "status": self.status,
            "candidate_action_kind": self.candidate_action_kind,
            "reviewed_incoming_tile_candidate":
                self.reviewed_incoming_tile_candidate,
            "shaded_face_index": self.shaded_face_index,
            # The event itself is only known to lie somewhere between an
            # independently observed preceding discard and NEW meld view.
            "possible_action_interval_frames": (
                [self.preceding_discard_frame, self.first_stable_meld_frame]
                if self.preceding_discard_frame is not None
                and self.first_stable_meld_frame is not None else None
            ),
            "shade_first_stable_frame": self.shade_first_stable_frame,
            "appearance_delay_frames_from_first_meld_view":
                self.appearance_delay_frames,
            "exact_action_frame": None,
            "actual_action_to_shade_delay": None,
            "requires_owner_event_truth_review": True,
            "requires_independent_automated_river_and_hand_delta": True,
            "production_incoming_tile_id": "UNKNOWN",
            "production_action_kind": "UNKNOWN",
            "actor": "UNKNOWN",
            "turn_actor": "UNKNOWN",
            "formal_promotion_evidence": False,
            "safe_for_runtime": False,
            "safe_for_executor": False,
            "issues": list(self.issues),
        }


def _unverified(reason: str, *, conflict: bool = False) -> DevelopmentMeldEventCandidate:
    return DevelopmentMeldEventCandidate(
        "CONFLICT" if conflict else "UNKNOWN",
        "UNKNOWN", None, None, None, None, None, None, (reason,),
    )


def _candidate_shape(ids: tuple[str, ...]) -> str:
    if len(ids) not in (3, 4) or any(
        not isinstance(x, str) or (not _NUMERIC.fullmatch(x) and x not in _HONORS)
        for x in ids
    ):
        return "UNKNOWN"
    if len(set(ids)) == 1:
        return "PENG_LIKE" if len(ids) == 3 else "KONG_LIKE"
    if len(ids) != 3:
        return "UNKNOWN"
    if not all(_NUMERIC.fullmatch(x) for x in ids):
        return "UNKNOWN"
    if len({x[0] for x in ids}) != 1:
        return "UNKNOWN"
    values = sorted(int(x[1:]) for x in ids)
    if values[1] == values[0] + 1 and values[2] == values[1] + 1:
        return "CHI_LIKE"
    return "UNKNOWN"


def cross_check_reviewed_meld_event(
    discard: ManuallyReviewedPublicDiscard,
    meld: ManuallyReviewedNewMeld,
    shade_frames: Sequence[SourceScopedShadeFrame],
    *,
    verified_fps: float | None = None,
) -> DevelopmentMeldEventCandidate:
    """Return only a candidate when ALL independent development gates hold.

    For CHI-like sequences, shade frames must cover the same exact
    SHA/session/epoch/track starting on the first stable reviewed group frame.
    For identical PENG/KONG-like groups, shade_frames may be empty because the
    UI has no useful positional distinction. An already-existing row merely
    changing appearance is NEVER a new event; no 'shadow first frame = CHI'
    inference and no 'no shade = PENG/KONG' inference.
    """
    if (
        not _SHA.fullmatch(discard.source_sha256)
        or discard.source_sha256 != meld.source_sha256
        or not discard.source_session
        or discard.source_session != meld.source_session
        or type(discard.stream_epoch) is not int
        or discard.stream_epoch < 0
        or discard.stream_epoch != meld.stream_epoch
        or not meld.meld_track_id
    ):
        return _unverified("source_session_sha_or_stream_epoch_conflict", conflict=True)
    if any(v is not True for v in (
        discard.original_video_sha_verified,
        discard.source_frame_pixel_verified,
        discard.explicit_tile_manually_reviewed,
        discard.no_intervening_public_action_reviewed,
        meld.original_video_sha_verified,
        meld.source_frame_pixel_verified,
        meld.user_approved_face_id_provenance,
        meld.independently_reviewed_absent_before_present,
    )):
        return _unverified("source_or_independent_transition_not_verified")
    if (
        discard.screen_side not in ("upper", "lower")
        or meld.screen_side not in ("upper", "lower")
        or discard.screen_side == meld.screen_side
    ):
        return _unverified("separate_discard_and_meld_screen_sides_required")
    if (
        type(discard.frame_index) is not int
        or type(meld.frame_index) is not int
        or discard.frame_index < 0
        or discard.frame_index >= meld.frame_index
    ):
        return _unverified("discard_must_precede_new_meld")
    shape = _candidate_shape(meld.face_ids_left_to_right)
    if shape == "UNKNOWN":
        return _unverified("unsupported_or_unverified_meld_shape")
    if not isinstance(discard.visible_tile_id, str) or not (
        _NUMERIC.fullmatch(discard.visible_tile_id)
        or discard.visible_tile_id in _HONORS
    ):
        return _unverified("preceding_discard_identity_unverified")

    # Owner-confirmed UI semantics: PENG/KONG use identical tiles, so there is
    # no meaningful "which tile came from the discard" position to mark.
    # Absence of shade must never count against an identical-tile claim.
    if shape in {"PENG_LIKE", "KONG_LIKE"}:
        claimed = meld.face_ids_left_to_right[0]
        if discard.visible_tile_id != claimed:
            return _unverified(
                "preceding_discard_vs_identical_meld_conflict", conflict=True
            )
        return DevelopmentMeldEventCandidate(
            "DEVELOPMENT_CORROBORATED_CANDIDATE",
            shape,
            claimed,
            None,
            discard.frame_index,
            meld.frame_index,
            None,
            None,
            (
                "identical_tile_claim_does_not_require_positional_shade",
                "directly_reviewed_source_frames_only_not_owner_event_truth",
            ),
        )

    # CHI-like groups contain three different suited tiles. The later shade is
    # therefore an optional positional UI cue that can corroborate which slot
    # corresponds to the preceding discard. It is follow-up evidence only.
    if not shade_frames or shade_frames[0].frame_index != meld.frame_index:
        return _unverified("no_same_track_shade_sequence_from_meld_baseline")
    expected = (
        meld.source_session, meld.source_sha256,
        meld.stream_epoch, meld.meld_track_id,
    )
    previous = meld.frame_index - 1
    for frame in shade_frames:
        if (
            (
                frame.source_session, frame.source_sha256,
                frame.stream_epoch, frame.meld_track_id,
            ) != expected
            or type(frame.frame_index) is not int
            or frame.frame_index != previous + 1
            or frame.reviewed_public_meld is not True
            or frame.regular_three_faces is not True
            or frame.exact_source_frame_verified is not True
        ):
            return _unverified("untrusted_shade_sequence_source_track_or_continuity")
        previous = frame.frame_index
    shade: DelayedShadeReview = review_delayed_shade(
        shade_frames, group_history="newly_observed",
        verified_video_fps=verified_fps,
    )
    if (
        shade.status != "DELAYED_SHADE_AFTER_MELD_APPEARANCE"
        or shade.shadow_index is None
        or shade.shade_first_observed_frame is None
    ):
        return _unverified("no_stable_later_same_track_shade")
    index = shade.shadow_index
    if index >= len(meld.face_ids_left_to_right):
        return _unverified("shaded_face_outside_reviewed_meld")
    claimed = meld.face_ids_left_to_right[index]
    if claimed != discard.visible_tile_id:
        return _unverified("preceding_discard_vs_shaded_face_conflict", conflict=True)
    return DevelopmentMeldEventCandidate(
        "DEVELOPMENT_CORROBORATED_CANDIDATE",
        shape,
        claimed,
        index,
        discard.frame_index,
        meld.frame_index,
        shade.shade_first_observed_frame,
        shade.observed_lag_frames,
        ("directly_reviewed_source_frames_only_not_owner_event_truth",),
    )
