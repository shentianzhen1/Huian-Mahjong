"""Issue #69: ORIGINAL-frame upper public raised-tile withdrawal diagnostic.

Search an independently trusted upper public-action region for a single tall
bright raised-tile-shaped COMPONENT before a source-adjacent frame transition
and its disappearance after. The 9 available videos are archived replays:
replay *transport* buttons are never used here. This signal observes public
tile-like geometry, not live button availability, tile identity or a claim.

Development-only, thresholds exploratory / calibrated on the SAME seven
previously selected original-video events: NEVER report 7/7 as accuracy.
Requires separate lower meld onset, discard ID, hand count and owner audit.
No concealed-hand shadows. Runtime, Hint, AI and Executor are unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re

from workspace.vision.public_meld_gap_onset import SourceScopedOpticalFrame

_SHA = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class RaisedPublicTileWithdrawal:
    status: str
    reason: str
    prior_frame: int | None = None
    after_frame: int | None = None
    prior_candidates: int | None = None
    after_candidates: int | None = None
    before_bbox: tuple[int, int, int, int] | None = None
    # PRIVATE source-scoped provenance for trusted cross-region joins.
    # This is intentionally omitted from public serialization.
    source_session: str | None = None
    source_sha256: str | None = None
    stream_epoch: int | None = None

    def to_dict(self) -> dict:
        # No original source hash, original video filename, player or crop.
        return {
            "schema_version": "public_raised_tile_withdrawal_dev_v0_1",
            "development_only": True,
            "status": self.status,
            "reason": self.reason,
            "adjacent_source_frames": (
                self.after_frame - self.prior_frame
                if self.prior_frame is not None
                and self.after_frame is not None else None
            ),
            "prior_candidates": self.prior_candidates,
            "after_candidates": self.after_candidates,
            "before_bbox": list(self.before_bbox) if self.before_bbox else None,
            "thresholds": "EXPLORATORY_SAME_SOURCE_NOT_BLIND",
            "public_raised_tile_shape_only": True,
            "replay_buttons_used": False,
            "concealed_hand_shadow_used": False,
            "actual_discard_identity": "UNKNOWN",
            "actual_claimed_meld": "UNKNOWN",
            "production_action_kind": "UNKNOWN",
            "owner_confirmed_action": False,
            "source_disjoint_promotion": False,
            "safe_for_runtime": False,
            "safe_for_executor": False,
        }


def _unknown(reason: str, pre: int | None = None,
             post: int | None = None) -> RaisedPublicTileWithdrawal:
    return RaisedPublicTileWithdrawal(
        "UNKNOWN", reason, prior_candidates=pre, after_candidates=post,
    )


def _raised_candidates(pixels):
    """Exploratory *shape-only* central-upper ROI; no game labels or hand ROI."""
    import cv2
    import numpy as np

    height, width = pixels.shape[:2]
    hsv = cv2.cvtColor(pixels, cv2.COLOR_BGR2HSV)
    mask = (
        (hsv[:, :, 1] < 130) & (hsv[:, :, 2] > 144)
    ).astype(np.uint8)
    # Normalize to the source frame. Top opponent concealed UI and all
    # lower player hand/draw/meld cards lie OUTSIDE this public-action band.
    mask[:round(height * .078), :] = 0
    mask[round(height * .36):, :] = 0
    mask[:, :round(width * .29)] = 0
    mask[:, round(width * .72):] = 0
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    result = []
    for x, y, w, h, area in stats[1:count]:
        if (
            area / (width * height) > .003
            and y / height < .145
            and h / height > .14
            and x / width < .70
            and (x + w) / width > .35
        ):
            result.append((int(x), int(y), int(w), int(h), int(area)))
    return sorted(result, key=lambda c: -c[4])


def probe_adjacent_raised_tile_withdrawal(
    before: SourceScopedOpticalFrame,
    after: SourceScopedOpticalFrame,
    *,
    upper_public_action_region_verified: bool,
    source_frames_unobscured_in_upper_region: bool,
) -> RaisedPublicTileWithdrawal:
    """A single earlier tall upper tile-like blob vanishes between two frames.

    This is not an OCR / tile-identity / actual-discard detector. Even a
    positive must NOT create a public action: a turn/animation/UI change
    may also cause disappearance. An independently observed matching
    discard and a fresh lower PUBLIC-MELD onset are separate requirements.
    """
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
        or upper_public_action_region_verified is not True
        or source_frames_unobscured_in_upper_region is not True
    ):
        return _unknown("source_scope_frame_or_public_region_unverified")
    for f in (before, after):
        pixels = f.bgr_pixels
        if (
            f.original_video_sha_verified is not True
            or f.original_decoded_frame_verified is not True
            or not isinstance(f.decoded_pixel_sha256, str)
            or not _SHA.fullmatch(f.decoded_pixel_sha256)
            or not isinstance(pixels, np.ndarray)
            or pixels.dtype != np.uint8
            or pixels.ndim != 3 or pixels.shape[2] != 3
            or hashlib.sha256(pixels.tobytes()).hexdigest()
            != f.decoded_pixel_sha256
        ):
            return _unknown("original_frame_pixel_or_checksum_unverified")
    a, b = before.bgr_pixels, after.bgr_pixels
    if a.shape != b.shape:
        return _unknown("source_resolution_changed")
    height, width = a.shape[:2]
    if width < 320 or height < 240:
        return _unknown("insufficient_source_resolution")
    if before.decoded_pixel_sha256 == after.decoded_pixel_sha256:
        return _unknown("identical_source_pixels_do_not_prove_withdrawal")
    pre, post = _raised_candidates(a), _raised_candidates(b)
    if len(pre) != 1:
        return _unknown("none_or_ambiguous_prior_upper_raised_tile", len(pre), len(post))
    if post:
        return _unknown("raised_upper_component_still_present_or_replaced",
                        len(pre), len(post))
    return RaisedPublicTileWithdrawal(
        "PUBLIC_RAISED_TILE_WITHDRAWAL_OPTICAL_CANDIDATE_ONLY",
        "one_source_upper_shape_disappears_in_adjacent_original_frame",
        prior_frame=before.frame_index,
        after_frame=after.frame_index,
        prior_candidates=1,
        after_candidates=0,
        before_bbox=pre[0][:4],
        source_session=before.source_session,
        source_sha256=before.source_sha256,
        stream_epoch=before.stream_epoch,
    )
