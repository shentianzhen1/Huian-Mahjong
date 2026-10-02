"""#69 source-scoped dense-river slot occupancy delta, development only.

Connected-component geometry can merge a dense river row into one bright blob.
This probe instead checks independently reviewed, normalized slot interiors.
The slot layout belongs in a private source manifest; no recording coordinates
or hashes are embedded here.

A positive result proves only a stable N -> N+1 public-river count transition.
It does not identify the tile, turn, action kind or canonical actor and never
emits a runtime RawObservation.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Sequence

from workspace.vision.public_action_area_transition_join import PublicTransitionFact
from workspace.vision.public_meld_gap_onset import SourceScopedOpticalFrame

_SHA = re.compile(r"^[a-f0-9]{64}$")
_ACTORS = frozenset(("player", "opponent"))


@dataclass(frozen=True)
class DenseRiverSlotProfile:
    actor: str
    slots: tuple[tuple[float, float, float, float], ...]
    maximum_saturation: int = 150
    minimum_value: int = 145
    empty_fraction_maximum: float = .12
    occupied_fraction_minimum: float = .42
    interior_trim_ratio: float = .12


@dataclass(frozen=True)
class DenseRiverCountDelta:
    status: str
    reason: str
    actor_hint: str = "UNKNOWN"
    before_count: int | None = None
    after_count: int | None = None
    delta: int | None = None
    first_stable_after_frame: int | None = None
    source_session: str | None = None
    source_sha256: str | None = None
    stream_epoch: int | None = None

    def to_dict(self) -> dict:
        return {
            "schema_version": "public_dense_river_slot_delta_dev_v0_1",
            "development_only": True,
            "status": self.status,
            "reason": self.reason,
            "actor_hint": self.actor_hint,
            "before_count": self.before_count,
            "after_count": self.after_count,
            "delta": self.delta,
            "tile_identity": "UNKNOWN",
            "actual_action_kind": "UNKNOWN",
            "actual_actor": "UNKNOWN",
            "source_coordinates_exposed": False,
            "raw_observation_emitted": False,
            "formal_accuracy_eligible": False,
            "safe_for_runtime": False,
            "safe_for_executor": False,
        }


@dataclass(frozen=True)
class DenseRiverSequenceAudit:
    status: str
    candidate_count_changes: tuple[tuple[int, int], ...]
    suppressed_reappearances: int
    ambiguous_or_disappearing_transitions: int

    def to_dict(self) -> dict:
        return {
            "schema_version": "public_dense_river_sequence_audit_dev_v0_1",
            "development_only": True,
            "status": self.status,
            "candidate_count_changes": [list(item) for item in self.candidate_count_changes],
            "suppressed_reappearances": self.suppressed_reappearances,
            "ambiguous_or_disappearing_transitions": (
                self.ambiguous_or_disappearing_transitions
            ),
            "slot_indexes_exposed": False,
            "actual_actions_emitted": 0,
            "safe_for_runtime": False,
            "safe_for_executor": False,
        }


@dataclass(frozen=True)
class DenseRiverPrefixSequenceAudit:
    status: str
    candidate_prefix_growth: tuple[tuple[int, int, int], ...]
    ambiguous_transitions: int
    suppressed_reappearances: int

    def to_dict(self) -> dict:
        return {
            "schema_version": "public_dense_river_prefix_sequence_dev_v0_1",
            "development_only": True,
            "status": self.status,
            "candidate_prefix_growth": [list(item) for item in self.candidate_prefix_growth],
            "ambiguous_transitions": self.ambiguous_transitions,
            "suppressed_reappearances": self.suppressed_reappearances,
            "actual_actions_emitted": 0,
            "tile_identity": "UNKNOWN",
            "actual_action_kind": "UNKNOWN",
            "formal_accuracy_eligible": False,
            "safe_for_runtime": False,
            "safe_for_executor": False,
        }


@dataclass(frozen=True)
class DenseRiverMaskFrame:
    """Ephemeral reviewed mask; construct from a verified decoded frame."""

    source_session: str
    source_sha256: str
    stream_epoch: int
    frame_index: int
    slot_mask: tuple[bool | None, ...]
    source_pixels_verified: bool


@dataclass(frozen=True)
class DenseRiverPrefixGrowth:
    """Stable occupied-prefix growth; total count may remain unknown."""

    status: str
    reason: str
    actor_hint: str = "UNKNOWN"
    before_confirmed_prefix: int | None = None
    after_confirmed_prefix: int | None = None
    first_stable_after_frame: int | None = None
    source_session: str | None = None
    source_sha256: str | None = None
    stream_epoch: int | None = None

    def to_dict(self) -> dict:
        return {
            "schema_version": "public_dense_river_prefix_growth_dev_v0_1",
            "development_only": True,
            "status": self.status,
            "reason": self.reason,
            "actor_hint": self.actor_hint,
            "before_confirmed_prefix": self.before_confirmed_prefix,
            "after_confirmed_prefix": self.after_confirmed_prefix,
            "exact_total_count_known": False,
            "tile_identity": "UNKNOWN",
            "actual_action_kind": "UNKNOWN",
            "actual_actor": "UNKNOWN",
            "raw_observation_emitted": False,
            "formal_accuracy_eligible": False,
            "safe_for_runtime": False,
            "safe_for_executor": False,
        }


def _unknown(reason: str, actor: str = "UNKNOWN") -> DenseRiverCountDelta:
    return DenseRiverCountDelta("UNKNOWN", reason, actor)


def _valid_profile(profile: DenseRiverSlotProfile) -> bool:
    if not isinstance(profile, DenseRiverSlotProfile) or profile.actor not in _ACTORS:
        return False
    if not 1 <= len(profile.slots) <= 32:
        return False
    if (
        type(profile.maximum_saturation) is not int
        or not 0 <= profile.maximum_saturation <= 255
        or type(profile.minimum_value) is not int
        or not 0 <= profile.minimum_value <= 255
    ):
        return False
    numeric = (
        profile.empty_fraction_maximum,
        profile.occupied_fraction_minimum,
        profile.interior_trim_ratio,
    )
    if any(
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not math.isfinite(value)
        for value in numeric
    ):
        return False
    if not (
        0 <= profile.empty_fraction_maximum
        < profile.occupied_fraction_minimum <= 1
        and 0 <= profile.interior_trim_ratio < .4
    ):
        return False
    for slot in profile.slots:
        if not isinstance(slot, tuple) or len(slot) != 4:
            return False
        if any(
            type(value) not in (int, float)
            or isinstance(value, bool)
            or not math.isfinite(value)
            for value in slot
        ):
            return False
        x, y, width, height = slot
        if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 1 or y + height > 1:
            return False
    # Reviewed slots are independent cells. Overlap would double-count pixels.
    for index, first in enumerate(profile.slots):
        for second in profile.slots[index + 1:]:
            overlap_x = max(0., min(first[0] + first[2], second[0] + second[2])
                            - max(first[0], second[0]))
            overlap_y = max(0., min(first[1] + first[3], second[1] + second[3])
                            - max(first[1], second[1]))
            if overlap_x * overlap_y > 1e-9:
                return False
    return True


def _valid_frame(frame: SourceScopedOpticalFrame) -> bool:
    import numpy as np

    pixels = frame.bgr_pixels
    return (
        isinstance(frame, SourceScopedOpticalFrame)
        and isinstance(frame.source_session, str) and bool(frame.source_session)
        and isinstance(frame.source_sha256, str) and bool(_SHA.fullmatch(frame.source_sha256))
        and type(frame.stream_epoch) is int and frame.stream_epoch >= 0
        and type(frame.frame_index) is int and frame.frame_index >= 0
        and frame.original_video_sha_verified is True
        and frame.original_decoded_frame_verified is True
        and isinstance(frame.decoded_pixel_sha256, str)
        and bool(_SHA.fullmatch(frame.decoded_pixel_sha256))
        and isinstance(pixels, np.ndarray)
        and pixels.dtype == np.uint8
        and pixels.ndim == 3 and pixels.shape[2] == 3
        and hashlib.sha256(pixels.tobytes()).hexdigest() == frame.decoded_pixel_sha256
    )


def _slot_state(frame: SourceScopedOpticalFrame, profile: DenseRiverSlotProfile):
    import cv2
    import numpy as np

    pixels = frame.bgr_pixels
    height, width = pixels.shape[:2]
    states: list[bool | None] = []
    for normalized in profile.slots:
        x = round(normalized[0] * width)
        y = round(normalized[1] * height)
        slot_width = round(normalized[2] * width)
        slot_height = round(normalized[3] * height)
        trim_x = round(slot_width * profile.interior_trim_ratio)
        trim_y = round(slot_height * profile.interior_trim_ratio)
        roi = pixels[
            y + trim_y:y + slot_height - trim_y,
            x + trim_x:x + slot_width - trim_x,
        ]
        if roi.shape[0] < 4 or roi.shape[1] < 4:
            return None
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        paper = (
            (hsv[:, :, 1] <= profile.maximum_saturation)
            & (hsv[:, :, 2] >= profile.minimum_value)
        )
        fraction = float(np.mean(paper))
        if fraction <= profile.empty_fraction_maximum:
            states.append(False)
        elif fraction >= profile.occupied_fraction_minimum:
            states.append(True)
        else:
            states.append(None)
    return tuple(states)


def source_scoped_dense_river_mask(
    frame: SourceScopedOpticalFrame,
    profile: DenseRiverSlotProfile,
) -> DenseRiverMaskFrame | None:
    """Verify original decoded pixels before retaining only slot states."""
    if not _valid_profile(profile) or not _valid_frame(frame):
        return None
    mask = _slot_state(frame, profile)
    if mask is None:
        return None
    return DenseRiverMaskFrame(
        frame.source_session, frame.source_sha256, frame.stream_epoch,
        frame.frame_index, mask, True,
    )


def _valid_mask_frame(frame: DenseRiverMaskFrame, slot_count: int) -> bool:
    return (
        isinstance(frame, DenseRiverMaskFrame)
        and frame.source_pixels_verified is True
        and isinstance(frame.source_session, str) and bool(frame.source_session)
        and isinstance(frame.source_sha256, str)
        and bool(_SHA.fullmatch(frame.source_sha256))
        and type(frame.stream_epoch) is int and frame.stream_epoch >= 0
        and type(frame.frame_index) is int and frame.frame_index >= 0
        and isinstance(frame.slot_mask, tuple)
        and len(frame.slot_mask) == slot_count
        and all(value is None or type(value) is bool for value in frame.slot_mask)
    )


def audit_dense_river_prefix_sequence(
    frames: Sequence[DenseRiverMaskFrame],
    *,
    profile: DenseRiverSlotProfile,
    slots_independently_reviewed: bool,
    stable_frames: int = 3,
) -> DenseRiverPrefixSequenceAudit:
    """Report new stable prefix cells, never public actions or exact totals.

    Reappearing cells and non-unit jumps are refused. Every decoded frame must
    be present so a source gap cannot quietly become a new growth candidate.
    """
    unknown = DenseRiverPrefixSequenceAudit("UNKNOWN", (), 0, 0)
    if (not _valid_profile(profile) or slots_independently_reviewed is not True
            or type(stable_frames) is not int or stable_frames < 3
            or not frames or any(not _valid_mask_frame(frame, len(profile.slots))
                                  for frame in frames)):
        return unknown
    first = frames[0]
    scope = (first.source_session, first.source_sha256, first.stream_epoch)
    if any(
        (later.source_session, later.source_sha256, later.stream_epoch) != scope
        or later.frame_index != earlier.frame_index + 1
        for earlier, later in zip(frames, frames[1:])
    ):
        return unknown

    def prefix(mask: tuple[bool | None, ...]) -> int:
        return next((i for i, value in enumerate(mask) if value is not True), len(mask))

    first_seen: dict[int, int] = {}
    stable_prefix: int | None = None
    candidates: list[tuple[int, int, int]] = []
    ambiguous = 0
    reappearances = 0
    for index, frame in enumerate(frames):
        for slot, value in enumerate(frame.slot_mask):
            if value is True:
                first_seen.setdefault(slot, frame.frame_index)
        if index + 1 < stable_frames:
            continue
        window = frames[index + 1 - stable_frames:index + 1]
        if any(item.slot_mask != frame.slot_mask for item in window):
            continue
        current = prefix(frame.slot_mask)
        if stable_prefix is None:
            stable_prefix = current
        elif current > stable_prefix:
            if (current == stable_prefix + 1
                    and first_seen[stable_prefix] == window[0].frame_index):
                candidates.append((window[0].frame_index, stable_prefix, current))
            elif current == stable_prefix + 1:
                reappearances += 1
            else:
                ambiguous += 1
            stable_prefix = current
        elif current < stable_prefix:
            ambiguous += 1
            stable_prefix = current
    return DenseRiverPrefixSequenceAudit(
        "DENSE_RIVER_PREFIX_SEQUENCE_CANDIDATES_ONLY",
        tuple(candidates), ambiguous, reappearances,
    )


def probe_anchor_local_river_prefix_growth(
    frames: Sequence[DenseRiverMaskFrame],
    *,
    profile: DenseRiverSlotProfile,
    anchor_frame: int,
    expected_before_prefix: int,
    max_followup_frames: int,
    river_slots_independently_verified: bool,
    interval_continuously_reviewed: bool,
    source_window_from_continuous_decode: bool,
    expected_prefix_from_prior_chain: bool,
    stable_frames: int = 3,
) -> DenseRiverPrefixGrowth:
    """Accept one stable occupied-prefix step without claiming exact count."""

    def unknown(reason: str) -> DenseRiverPrefixGrowth:
        actor = profile.actor if _valid_profile(profile) else "UNKNOWN"
        return DenseRiverPrefixGrowth("UNKNOWN", reason, actor)

    if not _valid_profile(profile):
        return unknown("invalid_source_scoped_dense_river_profile")
    if (
        type(anchor_frame) is not int or anchor_frame < 0
        or type(expected_before_prefix) is not int
        or not 0 <= expected_before_prefix < len(profile.slots)
        or type(max_followup_frames) is not int or max_followup_frames < 1
        or type(stable_frames) is not int or stable_frames < 3
    ):
        return unknown("invalid_prefix_anchor_window_or_stability")
    if any(flag is not True for flag in (
        river_slots_independently_verified,
        interval_continuously_reviewed,
        source_window_from_continuous_decode,
        expected_prefix_from_prior_chain,
    )):
        return unknown("prefix_source_or_prior_chain_unverified")
    if (not isinstance(frames, Sequence) or isinstance(frames, (str, bytes))
            or len(frames) < stable_frames * 2
            or any(not _valid_mask_frame(frame, len(profile.slots))
                   for frame in frames)):
        return unknown("invalid_or_insufficient_source_scoped_masks")
    first = frames[0]
    scope = (first.source_session, first.source_sha256, first.stream_epoch)
    if any(
        (frame.source_session, frame.source_sha256, frame.stream_epoch) != scope
        for frame in frames[1:]
    ):
        return unknown("source_session_sha_or_epoch_changed")
    if any(later.frame_index != earlier.frame_index + 1
           for earlier, later in zip(frames, frames[1:])):
        return unknown("prefix_window_frames_not_adjacent")
    if first.frame_index >= anchor_frame or frames[-1].frame_index <= anchor_frame:
        return unknown("anchor_not_inside_source_window")

    def prefix(mask):
        for index, value in enumerate(mask):
            if value is not True:
                return index
        return len(mask)

    values = tuple(prefix(frame.slot_mask) for frame in frames)
    runs = []
    start = 0
    for offset in range(1, len(values) + 1):
        if offset < len(values) and values[offset] == values[start]:
            continue
        if offset - start >= stable_frames:
            runs.append((frames[start].frame_index,
                         frames[offset - 1].frame_index, values[start]))
        start = offset
    before = tuple(run for run in runs if run[0] < anchor_frame)
    if not any(value == expected_before_prefix for _, _, value in before):
        return unknown("expected_stable_prefix_baseline_absent")
    if any(value > expected_before_prefix for _, _, value in before):
        return unknown("larger_prefix_preexists_review_anchor")
    expected_after = expected_before_prefix + 1
    after = tuple(run for run in runs
                  if run[0] > anchor_frame and run[2] == expected_after)
    if not after:
        return unknown("no_stable_plus_one_prefix_after_anchor")
    first_after = after[0][0]
    if first_after > anchor_frame + max_followup_frames:
        return unknown("prefix_growth_outside_anchor_window")
    if any(start > first_after and value != expected_after
           for start, _, value in runs):
        return unknown("stable_prefix_reversion_or_competing_growth")
    return DenseRiverPrefixGrowth(
        "DENSE_RIVER_PREFIX_GROWTH_CANDIDATE_ONLY",
        "stable_confirmed_prefix_increased_by_one_exact_count_unknown",
        profile.actor, expected_before_prefix, expected_after, first_after,
        first.source_session, first.source_sha256, first.stream_epoch,
    )


def dense_river_prefix_growth_to_transition_fact(
    growth: DenseRiverPrefixGrowth,
) -> PublicTransitionFact | None:
    """Adapt verified prefix growth to a public transition, never an action."""
    if (
        not isinstance(growth, DenseRiverPrefixGrowth)
        or growth.status != "DENSE_RIVER_PREFIX_GROWTH_CANDIDATE_ONLY"
        or growth.actor_hint not in _ACTORS
        or type(growth.before_confirmed_prefix) is not int
        or growth.after_confirmed_prefix != growth.before_confirmed_prefix + 1
        or type(growth.first_stable_after_frame) is not int
        or not isinstance(growth.source_session, str) or not growth.source_session
        or not isinstance(growth.source_sha256, str)
        or not _SHA.fullmatch(growth.source_sha256)
        or type(growth.stream_epoch) is not int or growth.stream_epoch < 0
    ):
        return None
    return PublicTransitionFact(
        "river", growth.actor_hint, growth.first_stable_after_frame,
        growth.source_session, growth.source_sha256, growth.stream_epoch, True,
    )


def probe_dense_river_count_delta(
    before_frames: Sequence[SourceScopedOpticalFrame],
    after_frames: Sequence[SourceScopedOpticalFrame],
    *,
    profile: DenseRiverSlotProfile,
    river_slots_independently_verified: bool,
    windows_unobscured: bool,
    intervening_frames_continuously_reviewed: bool,
    stable_frames: int = 3,
) -> DenseRiverCountDelta:
    """Require two stable slot masks and exactly one empty -> occupied cell."""
    if not _valid_profile(profile):
        return _unknown("invalid_source_scoped_dense_river_profile")
    if type(stable_frames) is not int or stable_frames < 3:
        return _unknown("invalid_stability_requirement", profile.actor)
    if any(flag is not True for flag in (
        river_slots_independently_verified,
        windows_unobscured,
        intervening_frames_continuously_reviewed,
    )):
        return _unknown("river_slots_or_source_interval_unverified", profile.actor)
    if (
        not isinstance(before_frames, Sequence)
        or isinstance(before_frames, (str, bytes))
        or not isinstance(after_frames, Sequence)
        or isinstance(after_frames, (str, bytes))
        or len(before_frames) < stable_frames
        or len(after_frames) < stable_frames
    ):
        return _unknown("insufficient_stable_river_frames", profile.actor)
    frames = tuple(before_frames) + tuple(after_frames)
    if any(not _valid_frame(frame) for frame in frames):
        return _unknown("source_pixels_unverified", profile.actor)
    first = frames[0]
    scope = (first.source_session, first.source_sha256, first.stream_epoch)
    if any(
        (frame.source_session, frame.source_sha256, frame.stream_epoch) != scope
        or frame.bgr_pixels.shape != first.bgr_pixels.shape
        for frame in frames[1:]
    ):
        return _unknown("source_session_sha_epoch_or_resolution_changed", profile.actor)
    for window in (tuple(before_frames), tuple(after_frames)):
        if any(
            later.frame_index != earlier.frame_index + 1
            for earlier, later in zip(window, window[1:])
        ):
            return _unknown("stable_window_frames_not_adjacent", profile.actor)
    if after_frames[0].frame_index <= before_frames[-1].frame_index:
        return _unknown("river_windows_not_forward_ordered", profile.actor)

    before_states = tuple(_slot_state(frame, profile) for frame in before_frames)
    after_states = tuple(_slot_state(frame, profile) for frame in after_frames)
    if any(state is None or any(value is None for value in state)
           for state in before_states + after_states):
        return _unknown("ambiguous_slot_occupancy", profile.actor)
    if len(set(before_states)) != 1 or len(set(after_states)) != 1:
        return _unknown("unstable_dense_river_slot_mask", profile.actor)
    before = before_states[0]
    after = after_states[0]
    appeared = tuple(
        index for index, (old, new) in enumerate(zip(before, after))
        if old is False and new is True
    )
    disappeared = tuple(
        index for index, (old, new) in enumerate(zip(before, after))
        if old is True and new is False
    )
    if len(appeared) != 1 or disappeared:
        return _unknown("not_exactly_one_stable_empty_to_occupied_slot", profile.actor)
    before_count = sum(before)
    after_count = sum(after)
    if after_count != before_count + 1:
        return _unknown("river_count_delta_not_plus_one", profile.actor)
    return DenseRiverCountDelta(
        "DENSE_RIVER_COUNT_DELTA_CANDIDATE_ONLY",
        "source_locked_stable_slot_count_increased_by_one_not_an_action",
        profile.actor,
        before_count,
        after_count,
        1,
        after_frames[0].frame_index,
        first.source_session,
        first.source_sha256,
        first.stream_epoch,
    )


def probe_anchor_local_river_growth(
    frames: Sequence[DenseRiverMaskFrame],
    *,
    profile: DenseRiverSlotProfile,
    anchor_frame: int,
    max_followup_frames: int,
    river_slots_independently_verified: bool,
    interval_continuously_reviewed: bool,
    new_slot_never_seen_in_epoch: bool,
    source_window_from_continuous_decode: bool,
    stable_frames: int = 3,
) -> DenseRiverCountDelta:
    """Audit one source-reviewed local window; never reset a live river state.

    The first and last masks must each be stable. All other stable masks must
    be one of those two, with no return to baseline after the new mask. Thus
    an overlay's persistent multi-slot jump or a disappearing tile fails
    closed, even when the endpoint count happens to be +1. Short ambiguous
    animation frames are permitted but do not themselves prove a transition.
    The anchor is a development review aid, not an action label.
    """
    if not _valid_profile(profile):
        return _unknown("invalid_source_scoped_dense_river_profile")
    if (
        type(anchor_frame) is not int or anchor_frame < 0
        or type(max_followup_frames) is not int or max_followup_frames < 1
        or type(stable_frames) is not int or stable_frames < 3
    ):
        return _unknown("invalid_anchor_window_or_stability", profile.actor)
    if (river_slots_independently_verified is not True
            or interval_continuously_reviewed is not True
            or new_slot_never_seen_in_epoch is not True
            or source_window_from_continuous_decode is not True):
        return _unknown("river_slots_or_source_interval_unverified", profile.actor)
    if (not isinstance(frames, Sequence) or isinstance(frames, (str, bytes))
            or len(frames) < stable_frames * 2):
        return _unknown("insufficient_stable_river_frames", profile.actor)
    if any(
        not _valid_mask_frame(frame, len(profile.slots))
        for frame in frames
    ):
        return _unknown("source_pixels_unverified", profile.actor)
    first = frames[0]
    scope = (first.source_session, first.source_sha256, first.stream_epoch)
    if any(
        (frame.source_session, frame.source_sha256, frame.stream_epoch) != scope
        for frame in frames[1:]
    ):
        return _unknown("source_session_sha_epoch_or_resolution_changed", profile.actor)
    if any(later.frame_index != earlier.frame_index + 1
           for earlier, later in zip(frames, frames[1:])):
        return _unknown("anchor_window_frames_not_adjacent", profile.actor)
    if (first.frame_index >= anchor_frame
            or frames[-1].frame_index <= anchor_frame):
        return _unknown("anchor_not_inside_source_window", profile.actor)

    masks = tuple(frame.slot_mask for frame in frames)
    baseline, final = masks[0], masks[-1]
    if (baseline is None or final is None
            or any(value is None for value in baseline + final)
            or any(mask != baseline for mask in masks[:stable_frames])
            or any(mask != final for mask in masks[-stable_frames:])):
        return _unknown("unstable_local_river_endpoints", profile.actor)

    appeared = [index for index, (old, new) in enumerate(zip(baseline, final))
                if old is False and new is True]
    if (len(appeared) != 1
            or any(old is True and new is False
                   for old, new in zip(baseline, final))):
        return _unknown("not_exactly_one_stable_empty_to_occupied_slot", profile.actor)

    # Only stable runs are evidence. Once the new mask is seen, a stable
    # baseline reappearance invalidates this isolated growth candidate.
    stable_states = []
    for start in range(len(masks) - stable_frames + 1):
        sample = masks[start]
        if (sample is not None and None not in sample
                and all(mask == sample for mask in masks[start:start + stable_frames])):
            stable_states.append((start, sample))
    if any(mask not in (baseline, final) for _, mask in stable_states):
        return _unknown("competing_stable_river_mask", profile.actor)
    first_final = next((start for start, mask in stable_states if mask == final), None)
    if (first_final is None or any(start > first_final and mask == baseline
                                  for start, mask in stable_states)):
        return _unknown("stable_river_reversion", profile.actor)
    transition_frame = first.frame_index + first_final
    if not (anchor_frame < transition_frame
            <= anchor_frame + max_followup_frames):
        return _unknown("river_growth_outside_anchor_window", profile.actor)
    return DenseRiverCountDelta(
        "DENSE_RIVER_COUNT_DELTA_CANDIDATE_ONLY",
        "local_stable_slot_growth_near_review_anchor_not_an_action",
        profile.actor, sum(baseline), sum(final), 1, transition_frame,
        first.source_session, first.source_sha256, first.stream_epoch,
    )


def dense_river_delta_to_transition_fact(
    delta: DenseRiverCountDelta,
) -> PublicTransitionFact | None:
    """Adapt only a verified +1 candidate to the isolated correlation layer."""
    if (
        not isinstance(delta, DenseRiverCountDelta)
        or delta.status != "DENSE_RIVER_COUNT_DELTA_CANDIDATE_ONLY"
        or delta.delta != 1
        or delta.actor_hint not in _ACTORS
        or type(delta.first_stable_after_frame) is not int
        or not isinstance(delta.source_session, str) or not delta.source_session
        or not isinstance(delta.source_sha256, str)
        or not _SHA.fullmatch(delta.source_sha256)
        or type(delta.stream_epoch) is not int or delta.stream_epoch < 0
    ):
        return None
    return PublicTransitionFact(
        "river",
        delta.actor_hint,
        delta.first_stable_after_frame,
        delta.source_session,
        delta.source_sha256,
        delta.stream_epoch,
        True,
    )


def audit_dense_river_stable_masks(
    stable_masks: Sequence[Sequence[bool]],
) -> DenseRiverSequenceAudit:
    """Suppress a slot reappearing after animation/removal as a new discard.

    The input contains already-stable masks in temporal order.  This audit is
    identity-free and does not infer claims.  Once a slot has ever been seen
    occupied in the capture epoch, its later reappearance cannot be counted as
    a new river growth without independent evidence.
    """
    if (
        not isinstance(stable_masks, Sequence)
        or isinstance(stable_masks, (str, bytes))
        or not stable_masks
    ):
        return DenseRiverSequenceAudit("UNKNOWN", (), 0, 0)
    masks = tuple(tuple(mask) for mask in stable_masks)
    width = len(masks[0])
    if (
        width < 1
        or any(len(mask) != width for mask in masks)
        or any(type(value) is not bool for mask in masks for value in mask)
    ):
        return DenseRiverSequenceAudit("UNKNOWN", (), 0, 0)

    previous = masks[0]
    ever_occupied = {index for index, value in enumerate(previous) if value}
    changes: list[tuple[int, int]] = []
    reappearances = 0
    ambiguous = 0
    for current in masks[1:]:
        if current == previous:
            continue
        appeared = {
            index for index, (old, new) in enumerate(zip(previous, current))
            if not old and new
        }
        disappeared = {
            index for index, (old, new) in enumerate(zip(previous, current))
            if old and not new
        }
        if disappeared or len(appeared) != 1:
            ambiguous += 1
        else:
            slot = next(iter(appeared))
            if slot in ever_occupied:
                reappearances += 1
            else:
                changes.append((sum(previous), sum(current)))
        ever_occupied.update(index for index, value in enumerate(current) if value)
        previous = current
    return DenseRiverSequenceAudit(
        "DENSE_RIVER_SEQUENCE_AUDIT_ONLY",
        tuple(changes),
        reappearances,
        ambiguous,
    )
