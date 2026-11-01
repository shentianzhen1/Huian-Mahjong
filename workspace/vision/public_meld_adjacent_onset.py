"""Issue #69: source-locked adjacent-frame PUBLIC-MELD appearance gate.

An already visible group merely developing shade, a concealed hand re-sort,
or replay animation cannot count as a new exposed meld. The caller must
independently decode/verify the original consecutive source frames and
classify the PUBLIC-MELD region without relying on hand brightness/shadows.

This pure verifier cannot inspect pixels or attest that an upstream human or
detector label is true; it rejects incomplete or inconsistent attestations.
It has no production, Hint, rule or Executor integration.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

_SHA = re.compile(r"^[a-f0-9]{64}$")
_TILES = re.compile(r"^(?:[MPS][1-9]|[ESWNRGB])$")


@dataclass(frozen=True)
class ObservedPublicMeldTrack:
    """Stable tracker identity independent of tile-label or shade brightness."""
    track_id: str
    face_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.track_id, str) or not self.track_id
            or not isinstance(self.face_ids, tuple)
            or len(self.face_ids) not in (3, 4)
            or any(not isinstance(x, str) or not _TILES.fullmatch(x)
                   for x in self.face_ids)
        ):
            raise ValueError("track must have a nonempty ID and 3/4 valid faces")


@dataclass(frozen=True)
class AdjacentPublicMeldSourceFrame:
    source_session: str
    source_sha256: str
    decoded_frame_sha256: str
    stream_epoch: int
    frame_index: int
    screen_side: str
    frame_size: tuple[int, int]
    public_meld_tracks: tuple[ObservedPublicMeldTrack, ...]
    original_video_sha_verified: bool
    original_frame_pixels_verified: bool
    public_meld_region_separated_from_hand_gold: bool
    explicit_source_public_meld_region_verified: bool
    is_unobscured_source_frame: bool


@dataclass(frozen=True)
class AdjacentMeldOnsetReview:
    status: str
    reason: str
    source_session: str | None = None
    source_sha256: str | None = None
    stream_epoch: int | None = None
    screen_side: str | None = None
    target_track_id: str | None = None
    target_face_ids: tuple[str, ...] = ()
    prior_frame: int | None = None
    first_visible_frame: int | None = None

    def to_dict(self) -> dict:
        # Preserve sensitive original SHA, frame bytes and local replay
        # identifiers in the caller's PRIVATE ledger, never public telemetry.
        return {
            "schema_version": "public_adjacent_meld_onset_dev_v0_1",
            "development_only": True,
            "status": self.status,
            "reason": self.reason,
            "original_adjacent_frame_delta": (
                self.first_visible_frame - self.prior_frame
                if self.first_visible_frame is not None
                and self.prior_frame is not None else None
            ),
            "hand_shadow_used": False,
            "late_shade_used_as_action_timestamp": False,
            "requires_independent_real_source_decode": True,
            "requires_independent_discard_hand_meld_corroboration": True,
            "owner_confirmed_action": False,
            "action_kind": "UNKNOWN",
            "incoming_tile_id": "UNKNOWN",
            "safe_for_runtime": False,
            "safe_for_executor": False,
        }


def _unknown(reason: str) -> AdjacentMeldOnsetReview:
    return AdjacentMeldOnsetReview("UNKNOWN", reason)


def review_adjacent_public_meld_onset(
    before: AdjacentPublicMeldSourceFrame,
    after: AdjacentPublicMeldSourceFrame,
    *,
    target_track_id: str,
    approved_target_face_ids: tuple[str, ...],
) -> AdjacentMeldOnsetReview:
    """Gate a visible change; never infer actual CHI/PENG/KONG from one cue.

    Both frames MUST be actual consecutive decoded original-video frames.
    The PUBLIC-MELD region and existing track continuity must be verified
    independently of prompt text, concealed-hand shade and later meld shade.
    """
    if (
        not isinstance(target_track_id, str) or not target_track_id
        or not isinstance(approved_target_face_ids, tuple)
        or len(approved_target_face_ids) not in (3, 4)
        or any(not isinstance(x, str) or not _TILES.fullmatch(x)
               for x in approved_target_face_ids)
    ):
        return _unknown("invalid_target_identity_or_track")

    frames = (before, after)
    for frame in frames:
        if (
            not isinstance(frame.source_session, str) or not frame.source_session
            or not isinstance(frame.source_sha256, str)
            or not _SHA.fullmatch(frame.source_sha256)
            or not isinstance(frame.decoded_frame_sha256, str)
            or not _SHA.fullmatch(frame.decoded_frame_sha256)
            or type(frame.stream_epoch) is not int or frame.stream_epoch < 0
            or type(frame.frame_index) is not int or frame.frame_index < 0
            or frame.screen_side not in ("upper", "lower")
            or not isinstance(frame.frame_size, tuple)
            or len(frame.frame_size) != 2
            or any(type(x) is not int or x <= 0 for x in frame.frame_size)
            or not isinstance(frame.public_meld_tracks, tuple)
            or any(not isinstance(x, ObservedPublicMeldTrack)
                   for x in frame.public_meld_tracks)
        ):
            return _unknown("invalid_source_frame_or_public_track_contract")
        if any(x is not True for x in (
            frame.original_video_sha_verified,
            frame.original_frame_pixels_verified,
            frame.public_meld_region_separated_from_hand_gold,
            frame.explicit_source_public_meld_region_verified,
            frame.is_unobscured_source_frame,
        )):
            return _unknown("unverified_source_pixels_or_public_meld_roi")
        ids = [t.track_id for t in frame.public_meld_tracks]
        if len(set(ids)) != len(ids):
            return _unknown("ambiguous_duplicate_track_ids")

    if (
        before.source_session != after.source_session
        or before.source_sha256 != after.source_sha256
        or before.stream_epoch != after.stream_epoch
        or before.screen_side != after.screen_side
        or before.frame_size != after.frame_size
    ):
        return _unknown("source_epoch_side_or_resolution_changed")
    if after.frame_index != before.frame_index + 1:
        return _unknown("not_adjacent_original_source_frames")
    if before.decoded_frame_sha256 == after.decoded_frame_sha256:
        return _unknown("identical_pixels_cannot_show_new_group")

    previous = {x.track_id: x.face_ids for x in before.public_meld_tracks}
    current = {x.track_id: x.face_ids for x in after.public_meld_tracks}
    if target_track_id in previous:
        return AdjacentMeldOnsetReview(
            "PREEXISTING_MELD_NO_NEW_ACTION",
            "target_track_was_already_visible_before",
        )
    if any(
        tuple(ids) == approved_target_face_ids for ids in previous.values()
    ):
        # An already-exposed identical group may have been re-tracked. Do
        # not count re-ID/shading/ROI movement as a fresh claim.
        return _unknown("same_face_group_preexisted_with_another_track_id")
    if (
        target_track_id not in current
        or current[target_track_id] != approved_target_face_ids
    ):
        return _unknown("target_group_missing_or_face_identity_unverified")
    if (
        not all(current.get(track_id) == face_ids
                for track_id, face_ids in previous.items())
        or set(current) - set(previous) != {target_track_id}
    ):
        return _unknown("other_public_meld_tracks_changed_or_appeared")

    return AdjacentMeldOnsetReview(
        "NEW_MELD_VISUALLY_BRACKETED_OWNER_ACTION_PENDING",
        "one_new_stable_public_group_between_adjacent_original_frames",
        source_session=after.source_session,
        source_sha256=after.source_sha256,
        stream_epoch=after.stream_epoch,
        screen_side=after.screen_side,
        target_track_id=target_track_id,
        target_face_ids=approved_target_face_ids,
        prior_frame=before.frame_index,
        first_visible_frame=after.frame_index,
    )
