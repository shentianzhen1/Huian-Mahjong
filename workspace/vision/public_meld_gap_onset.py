"""#69: development-only optical gap diagnostic at an approved public meld ROI.

Does a newly separated group-like gap appear between *adjacent original*
frames at a source-locked bottom PUBLIC MELD location? This is NOT a
tile classifier or an action detector. A flower row, existing exposed group,
hand resort, visual shading or different source can confound it. Source
provenance / region truth is independently supplied, not inferred from
brightness. A positive still requires the strict adjacent-meld-onset,
river, hand and meld gates before manual action review.

OpenCV/numpy are optional Vision dependencies. No raw source frames are
serialized, saved, transmitted or exposed to the Runtime/Executor.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re

_SHA = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True, eq=False)
class SourceScopedOpticalFrame:
    source_session: str
    source_sha256: str
    stream_epoch: int
    frame_index: int
    decoded_pixel_sha256: str
    bgr_pixels: object
    original_video_sha_verified: bool
    original_decoded_frame_verified: bool


@dataclass(frozen=True)
class PublicMeldGapProbe:
    status: str
    reason: str
    longest_pre_gap_px: int | None = None
    longest_post_gap_px: int | None = None

    def to_dict(self) -> dict:
        return {
            "schema_version": "public_meld_gap_onset_dev_v0_1",
            "development_only": True,
            "status": self.status,
            "reason": self.reason,
            "preexisting_gap_pixels": self.longest_pre_gap_px,
            "new_candidate_gap_pixels": self.longest_post_gap_px,
            "calibration": "EXPLORATORY_NOT_SOURCE_DISJOINT",
            "real_action_kind": "UNKNOWN",
            "incoming_tile": "UNKNOWN",
            "hand_shadow_used_as_eligibility_signal": False,
            "public_meld_region_independently_required": True,
            "safe_for_runtime": False,
            "safe_for_executor": False,
        }


def _fail(reason: str, *, pre: int | None = None,
          post: int | None = None) -> PublicMeldGapProbe:
    return PublicMeldGapProbe("UNKNOWN", reason, pre, post)


def probe_adjacent_group_gap(
    before: SourceScopedOpticalFrame,
    after: SourceScopedOpticalFrame,
    *,
    approved_late_group_bbox: tuple[int, int, int, int],
    public_meld_roi_independently_verified: bool,
    late_group_bbox_source_locked: bool,
    gap_min_px: int | None = None,
) -> PublicMeldGapProbe:
    """Detect a NEW background gap at a previously reviewed public-meld edge.

    Bbox is the earlier independently APPROVED *later* public group geometry;
    it must not be guessed by this pixel probe. The expected result is a
    weak lower-level visual signal only: grouping/tile identities and every
    actual action remain UNKNOWN. Values are provisional same-source
    diagnostic thresholds, never claimed as general accuracy.
    """
    import cv2
    import numpy as np

    if (
        not isinstance(before.source_session, str) or not before.source_session
        or before.source_session != after.source_session
        or not isinstance(before.source_sha256, str)
        or not _SHA.fullmatch(before.source_sha256)
        or before.source_sha256 != after.source_sha256
        or type(before.stream_epoch) is not int or before.stream_epoch < 0
        or before.stream_epoch != after.stream_epoch
        or type(before.frame_index) is not int or before.frame_index < 0
        or type(after.frame_index) is not int
        or after.frame_index != before.frame_index + 1
        or public_meld_roi_independently_verified is not True
        or late_group_bbox_source_locked is not True
    ):
        return _fail("source_scope_frame_continuity_or_public_roi_unverified")
    imgs = (before, after)
    for obj in imgs:
        pixels = obj.bgr_pixels
        if (
            obj.original_video_sha_verified is not True
            or obj.original_decoded_frame_verified is not True
            or not isinstance(obj.decoded_pixel_sha256, str)
            or not _SHA.fullmatch(obj.decoded_pixel_sha256)
            or not isinstance(pixels, np.ndarray)
            or pixels.ndim != 3 or pixels.shape[2] != 3
            or pixels.dtype != np.uint8
            or hashlib.sha256(pixels.tobytes()).hexdigest()
            != obj.decoded_pixel_sha256
        ):
            return _fail("decoded_original_pixels_or_source_hash_unverified")
    first, second = (obj.bgr_pixels for obj in imgs)
    if first.shape != second.shape:
        return _fail("source_frame_resolution_changed")
    if before.decoded_pixel_sha256 == after.decoded_pixel_sha256:
        return _fail("identical_decoded_pixels_do_not_prove_new_group")
    if (
        not isinstance(approved_late_group_bbox, tuple)
        or len(approved_late_group_bbox) != 4
        or any(type(a) is not int for a in approved_late_group_bbox)
    ):
        return _fail("invalid_approved_group_bbox")
    x, y, width, height = approved_late_group_bbox
    H, W = first.shape[:2]
    if (
        x < 0 or y < 0 or width < 30 or height < 30
        or x + width > W or y + height > H
        or x + width + 46 >= W
    ):
        return _fail("group_bbox_or_gap_probe_outside_original_frame")
    if gap_min_px is None:
        gap_min_px = max(14, round(width * .14))
    if type(gap_min_px) is not int or gap_min_px < 10:
        raise ValueError("gap_min_px must be an integer >= 10")

    # Look only for a teal-background gap at the *public-meld edge*.
    # This never interprets dimmed concealed tiles as playable/blocked.
    end = x + width
    lo, hi = end - 12, end + 47
    y0 = y + round(height * .16)
    y1 = y + height - round(height * .12)
    if y1 <= y0 or lo < 0 or hi > W:
        return _fail("degenerate_public_meld_edge_probe")
    measured = []
    for pixels in (first, second):
        hsv = cv2.cvtColor(pixels[y0:y1, :, :], cv2.COLOR_BGR2HSV)
        # Provisional in-source diagnostic, NOT a trained tile/shade model.
        paper = (hsv[..., 2] > 137) & (hsv[..., 1] < 116)
        column_coverage = paper.mean(axis=0)
        smoothed = np.convolve(column_coverage, np.ones(5) / 5, mode="same")
        low = smoothed[lo:hi] < .35
        spans = []
        start = None
        for i, val in enumerate(low):
            if val and start is None:
                start = lo + i
            if not val and start is not None:
                spans.append((start, lo + i - 1))
                start = None
        if start is not None:
            spans.append((start, hi - 1))
        measured.append(spans)

    pre = max((b - a + 1 for a, b in measured[0]
               if a <= end + 6 and b >= end - 6), default=0)
    post = max((b - a + 1 for a, b in measured[1]
                if end - 9 <= a <= end + 6
                and b >= end + 10), default=0)
    if pre >= gap_min_px:
        return _fail(
            "existing_separator_or_flower_row_already_present",
            pre=pre, post=post,
        )
    if post < gap_min_px:
        return _fail(
            "no_new_source_bound_separator_at_public_meld_edge",
            pre=pre, post=post,
        )
    return PublicMeldGapProbe(
        "NEW_EDGE_GAP_DEVELOPMENT_CANDIDATE_ONLY",
        "adjacent_source_frames_show_new_edge_gap_not_an_action",
        pre, post,
    )
