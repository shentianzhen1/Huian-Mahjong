"""#69 source-scoped public action-area onset candidate, development only.

This probe observes a new paper/tile-shaped component between adjacent source
frames in an independently reviewed public animation corridor.  It is not a
discard, tile-identity or action-kind detector: a UI animation may produce the
same geometry.  A positive remains a review candidate until an independent
river/meld/hand transition joins it.

Calibration profiles are resolution-relative and source-scoped.  Private
recording coordinates belong in ignored manifests, never in this module.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import re

from workspace.vision.public_meld_gap_onset import SourceScopedOpticalFrame

_SHA = re.compile(r"^[a-f0-9]{64}$")
_ACTORS = frozenset(("player", "opponent"))


@dataclass(frozen=True)
class ActionAreaProfile:
    """Source-reviewed normalized regions and tile-shape bounds."""

    actor: str
    onset_region: tuple[float, float, float, float]
    confirmation_region: tuple[float, float, float, float]
    width_ratio: tuple[float, float]
    height_ratio: tuple[float, float]
    area_ratio: tuple[float, float]
    aspect_ratio: tuple[float, float] = (.65, 2.5)
    centroid_motion_ratio: tuple[float, float] = (0.0, 1.0)


@dataclass(frozen=True)
class ActionAreaOnsetCandidate:
    status: str
    reason: str
    region_actor_hint: str | None = None
    prior_frame: int | None = None
    first_visible_frame: int | None = None
    confirmation_frame: int | None = None
    onset_bbox: tuple[int, int, int, int] | None = None
    confirmation_bbox: tuple[int, int, int, int] | None = None
    source_session: str | None = None
    source_sha256: str | None = None
    stream_epoch: int | None = None

    def to_dict(self) -> dict:
        # Deliberately omit source identifiers, exact frame indexes and bboxes.
        return {
            "schema_version": "public_action_area_onset_dev_v0_1",
            "development_only": True,
            "status": self.status,
            "reason": self.reason,
            "region_actor_hint": self.region_actor_hint or "UNKNOWN",
            "first_visible_after_prior_frames": (
                self.first_visible_frame - self.prior_frame
                if self.first_visible_frame is not None
                and self.prior_frame is not None else None
            ),
            "confirmation_after_first_visible_frames": (
                self.confirmation_frame - self.first_visible_frame
                if self.confirmation_frame is not None
                and self.first_visible_frame is not None else None
            ),
            "tile_identity": "UNKNOWN",
            "actual_action_kind": "UNKNOWN",
            "actual_actor": "UNKNOWN",
            "river_or_meld_join_required": True,
            "owner_confirmed_action": False,
            "source_disjoint_promotion": False,
            "safe_for_runtime": False,
            "safe_for_executor": False,
        }


def _unknown(reason: str, actor: str | None = None) -> ActionAreaOnsetCandidate:
    return ActionAreaOnsetCandidate("UNKNOWN", reason, actor)


def _range_ok(value, *, allow_zero: bool = False) -> bool:
    return (
        isinstance(value, tuple) and len(value) == 2
        and all(type(v) in (int, float) and not isinstance(v, bool)
                and math.isfinite(v) for v in value)
        and (0 <= value[0] if allow_zero else 0 < value[0])
        and value[0] <= value[1]
    )


def _profile_valid(profile: ActionAreaProfile) -> bool:
    if not isinstance(profile, ActionAreaProfile) or profile.actor not in _ACTORS:
        return False
    for region in (profile.onset_region, profile.confirmation_region):
        if (
            not isinstance(region, tuple) or len(region) != 4
            or any(type(v) not in (int, float) or isinstance(v, bool)
                   or not math.isfinite(v) for v in region)
        ):
            return False
        x, y, width, height = region
        if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 1 or y + height > 1:
            return False
    return (
        all(_range_ok(value) for value in (
            profile.width_ratio, profile.height_ratio,
            profile.area_ratio, profile.aspect_ratio,
        ))
        and _range_ok(profile.centroid_motion_ratio, allow_zero=True)
    )


def _frame_valid(frame: SourceScopedOpticalFrame) -> bool:
    import numpy as np

    pixels = frame.bgr_pixels
    return (
        isinstance(frame.source_session, str) and bool(frame.source_session)
        and isinstance(frame.source_sha256, str) and bool(_SHA.fullmatch(frame.source_sha256))
        and type(frame.stream_epoch) is int and frame.stream_epoch >= 0
        and type(frame.frame_index) is int and frame.frame_index >= 0
        and frame.original_video_sha_verified is True
        and frame.original_decoded_frame_verified is True
        and isinstance(frame.decoded_pixel_sha256, str)
        and bool(_SHA.fullmatch(frame.decoded_pixel_sha256))
        and isinstance(pixels, np.ndarray) and pixels.dtype == np.uint8
        and pixels.ndim == 3 and pixels.shape[2] == 3
        and hashlib.sha256(pixels.tobytes()).hexdigest() == frame.decoded_pixel_sha256
    )


def _paper_mask(pixels, region):
    import cv2
    import numpy as np

    height, width = pixels.shape[:2]
    x = int(round(region[0] * width))
    y = int(round(region[1] * height))
    right = int(round((region[0] + region[2]) * width))
    bottom = int(round((region[1] + region[3]) * height))
    roi = pixels[y:bottom, x:right]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = ((hsv[:, :, 1] < 140) & (hsv[:, :, 2] > 145)).astype(np.uint8)
    return mask, (x, y)


def _new_tile_components(baseline, current, region, profile):
    import cv2
    import numpy as np

    before, origin = _paper_mask(baseline, region)
    after, _ = _paper_mask(current, region)
    # Ignore the antialiased edge jitter of persistent public tiles/text.
    persistent = cv2.dilate(before, np.ones((3, 3), dtype=np.uint8))
    appeared = (after.astype(bool) & ~persistent.astype(bool)).astype(np.uint8)
    count, _, stats, _ = cv2.connectedComponentsWithStats(appeared, 8)
    frame_height, frame_width = baseline.shape[:2]
    frame_area = frame_width * frame_height
    candidates = []
    for x, y, width, height, area in stats[1:count]:
        width_ratio = width / frame_width
        height_ratio = height / frame_height
        area_ratio = area / frame_area
        aspect = height / max(width, 1)
        fill = area / max(width * height, 1)
        if (
            profile.width_ratio[0] <= width_ratio <= profile.width_ratio[1]
            and profile.height_ratio[0] <= height_ratio <= profile.height_ratio[1]
            and profile.area_ratio[0] <= area_ratio <= profile.area_ratio[1]
            and profile.aspect_ratio[0] <= aspect <= profile.aspect_ratio[1]
            and fill >= .35
        ):
            candidates.append((origin[0] + int(x), origin[1] + int(y),
                               int(width), int(height), int(area)))
    return sorted(candidates, key=lambda item: -item[4])


def probe_action_area_onset(
    before: SourceScopedOpticalFrame,
    first_visible: SourceScopedOpticalFrame,
    confirmation: SourceScopedOpticalFrame,
    *,
    profile: ActionAreaProfile,
    action_regions_independently_verified: bool,
    source_frames_unobscured: bool,
) -> ActionAreaOnsetCandidate:
    """Return a fail-closed animation-geometry candidate from three frames."""
    if not _profile_valid(profile):
        return _unknown("invalid_source_scoped_action_area_profile")
    frames = (before, first_visible, confirmation)
    if (
        action_regions_independently_verified is not True
        or source_frames_unobscured is not True
        or any(not isinstance(frame, SourceScopedOpticalFrame) for frame in frames)
        or any(not _frame_valid(frame) for frame in frames)
    ):
        return _unknown("source_pixels_or_action_regions_unverified", profile.actor)
    source = (before.source_session, before.source_sha256, before.stream_epoch)
    if any((frame.source_session, frame.source_sha256, frame.stream_epoch) != source
           for frame in frames[1:]):
        return _unknown("source_session_sha_or_epoch_changed", profile.actor)
    if (
        first_visible.frame_index != before.frame_index + 1
        or confirmation.frame_index != first_visible.frame_index + 1
    ):
        return _unknown("source_frames_not_three_adjacent_frames", profile.actor)
    if any(frame.bgr_pixels.shape != before.bgr_pixels.shape for frame in frames[1:]):
        return _unknown("source_resolution_changed", profile.actor)
    height, width = before.bgr_pixels.shape[:2]
    if width < 320 or height < 240:
        return _unknown("insufficient_source_resolution", profile.actor)
    if before.decoded_pixel_sha256 == first_visible.decoded_pixel_sha256:
        return _unknown("no_pixel_change_at_claimed_first_visible_frame", profile.actor)

    onset = _new_tile_components(
        before.bgr_pixels, first_visible.bgr_pixels,
        profile.onset_region, profile,
    )
    confirmed = _new_tile_components(
        before.bgr_pixels, confirmation.bgr_pixels,
        profile.confirmation_region, profile,
    )
    if len(onset) != 1:
        return _unknown("none_or_ambiguous_first_visible_tile_shape", profile.actor)
    if len(confirmed) != 1:
        return _unknown("tile_shape_not_uniquely_present_in_confirmation_frame", profile.actor)
    onset_box, confirmed_box = onset[0], confirmed[0]
    onset_center = (onset_box[0] + onset_box[2] / 2,
                    onset_box[1] + onset_box[3] / 2)
    confirmed_center = (confirmed_box[0] + confirmed_box[2] / 2,
                        confirmed_box[1] + confirmed_box[3] / 2)
    motion_ratio = math.hypot(
        confirmed_center[0] - onset_center[0],
        confirmed_center[1] - onset_center[1],
    ) / width
    if not (profile.centroid_motion_ratio[0] <= motion_ratio
            <= profile.centroid_motion_ratio[1]):
        return _unknown("candidate_motion_outside_source_profile", profile.actor)
    return ActionAreaOnsetCandidate(
        "ACTION_AREA_ONSET_CANDIDATE_ONLY",
        "new_source_scoped_tile_shape_persists_for_confirmation_not_an_action",
        profile.actor,
        before.frame_index,
        first_visible.frame_index,
        confirmation.frame_index,
        onset_box[:4],
        confirmed_box[:4],
        before.source_session,
        before.source_sha256,
        before.stream_epoch,
    )


def collapse_action_area_onset_candidates(
    candidates,
    *,
    minimum_event_separation_frames: int = 12,
) -> tuple[ActionAreaOnsetCandidate, ...]:
    """Keep the first frame of each same-source animation burst.

    This only deduplicates already emitted candidate geometry.  It never
    upgrades a candidate into an action and must be called separately for
    each independently mapped actor region.
    """
    if (type(minimum_event_separation_frames) is not int
            or minimum_event_separation_frames < 2):
        raise ValueError("minimum_event_separation_frames must be integer >= 2")
    items = tuple(candidates)
    if not items:
        return ()
    if any(not isinstance(item, ActionAreaOnsetCandidate) for item in items):
        raise ValueError("candidates must contain ActionAreaOnsetCandidate values")
    if any(item.status != "ACTION_AREA_ONSET_CANDIDATE_ONLY" for item in items):
        raise ValueError("only positive onset candidates can be collapsed")
    first = items[0]
    source = (first.source_session, first.source_sha256,
              first.stream_epoch, first.region_actor_hint)
    if any((item.source_session, item.source_sha256, item.stream_epoch,
            item.region_actor_hint) != source for item in items):
        raise ValueError("candidate source, epoch and actor region must match")
    if any(type(item.first_visible_frame) is not int for item in items):
        raise ValueError("candidate first-visible frames must be integers")
    if any(later.first_visible_frame <= earlier.first_visible_frame
           for earlier, later in zip(items, items[1:])):
        raise ValueError("candidates must be strictly frame ordered")
    kept = [first]
    for item in items[1:]:
        if (item.first_visible_frame - kept[-1].first_visible_frame
                >= minimum_event_separation_frames):
            kept.append(item)
    return tuple(kept)
