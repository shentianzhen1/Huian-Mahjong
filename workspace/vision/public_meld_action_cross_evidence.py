"""Issue #69: strict DEVELOPMENT-ONLY cross-evidence for delayed meld shading.

Independent preceding visible discard -> first reviewed three-face public meld
-> same-track LATER SHADE. The face-wide shadow appears AFTER the action and
MUST NOT be used as the action time. A successful result is an assistant-reviewed
candidate for a future owner audit, never a runtime action or blind accuracy.

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
    if len(ids) != 3 or any(
        not isinstance(x, str) or (not _NUMERIC.fullmatch(x) and x not in _HONORS)
        for x in ids
    ):
        return "UNKNOWN"
    if ids[0] == ids[1] == ids[2]:
        return "PENG_LIKE"
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

    Shade frames must cover the same exact SHA/session/epoch/track, starting
    on the first stable manually reviewed group frame. Use consecutive source
    frames (or this function abstains). An already-existing row merely changing
    appearance is NEVER a new event; no 'shadow first frame = CHI' inference.
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
    if not isinstance(discard.visible_tile_id, str) or not (
        _NUMERIC.fullmatch(discard.visible_tile_id)
        or discard.visible_tile_id in _HONORS
    ):
        return _unverified("preceding_discard_identity_unverified")
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
