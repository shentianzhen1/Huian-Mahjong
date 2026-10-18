"""Issue #69: geometry normalization for exposed meld groups.

This layer is deliberately geometry-only. It rectifies a detected meld crop,
normalizes scale, separates regular flat three-face rows, and emits a
fail-closed stacked-layout state. It does not infer tile identity or promote
CHI/PENG/MING_GANG into runtime truth.

The UI can render player/opponent melds at different sizes. Geometry is
therefore measured inside each detected group instead of assuming one global
pixel size.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from workspace.vision.public_tile_detector import PublicGeometryCandidate


FLAT = "FLAT"
STACKED = "STACKED"
UNKNOWN = "UNKNOWN"

# Development-only geometry gates. Stacked layouts need BOTH vertical excess
# and a narrow upper lobe; this avoids treating a tall but ordinary PENG crop
# as a Kong merely because its reviewed bbox has extra border/shadow.
_STACKED_MIN_HEIGHT_SCORE = 1.58
_STACKED_MAX_TOP_TO_MID = 0.60
_STACKED_STRONG_HEIGHT_SCORE = 1.90
_STACKED_STRONG_HEIGHT_MAX_TOP_TO_MID = 0.78
_FLAT_MAX_HEIGHT_SCORE = 1.80
_FLAT_MIN_TOP_TO_MID = 0.72
_CANONICAL_HEIGHT = 96


@dataclass(frozen=True)
class PublicMeldGeometryAnalysis:
    rotation_degrees: float
    stack_state: str
    height_score: float | None
    top_to_mid_span_ratio: float | None
    normalized_size: tuple[int, int]
    tight_bbox_in_group: tuple[int, int, int, int] | None
    issues: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "schema_version": "public_meld_geometry_normalization_v0_1",
            "rotation_degrees": self.rotation_degrees,
            "stack_state": self.stack_state,
            "height_score": self.height_score,
            "top_to_mid_span_ratio": self.top_to_mid_span_ratio,
            "normalized_size": list(self.normalized_size),
            "tight_bbox_in_group": (
                list(self.tight_bbox_in_group)
                if self.tight_bbox_in_group is not None else None
            ),
            "issues": list(self.issues),
            "geometry_only": True,
            "tile_identity": "UNKNOWN",
            "action_kind": "UNKNOWN",
            "safe_for_hint": False,
            "safe_for_executor": False,
        }


@dataclass(frozen=True)
class NormalizedPublicMeld:
    """Normalized in-memory crop plus geometry-only audit metadata."""

    image: Any
    analysis: PublicMeldGeometryAnalysis


def _unknown(reason: str) -> PublicMeldGeometryAnalysis:
    return PublicMeldGeometryAnalysis(
        rotation_degrees=0.0,
        stack_state=UNKNOWN,
        height_score=None,
        top_to_mid_span_ratio=None,
        normalized_size=(0, 0),
        tight_bbox_in_group=None,
        issues=(reason,),
    )


def _row_angle(rect: tuple) -> float:
    """Convert OpenCV minAreaRect angle to a small row deskew angle."""
    (_, _), (width, height), angle = rect
    if width <= 0 or height <= 0:
        return 0.0
    if width < height:
        angle += 90.0
    while angle > 45.0:
        angle -= 90.0
    while angle < -45.0:
        angle += 90.0
    return float(angle)


def _mean_nonzero(values: Any) -> float:
    selected = values[values > 0]
    return float(selected.mean()) if len(selected) else 0.0


def _stack_features(mask: Any) -> tuple[float, float]:
    """Return (height_score, top/middle occupied-span ratio).

    `height_score` expresses total group height in units of one of three base
    face widths. `top/middle` detects the narrow upper lobe produced by the
    overlaid fourth face. Width is measured from first to last bright pixel per
    row so internal glyph gaps do not masquerade as tile separators.
    """
    import numpy as np

    height, width = mask.shape[:2]
    if width <= 0 or height <= 0:
        return 0.0, 0.0

    spans = np.zeros(height, dtype=np.float32)
    for row_index, row in enumerate(mask):
        xs = np.flatnonzero(row)
        if len(xs):
            spans[row_index] = (int(xs[-1]) - int(xs[0]) + 1) / width

    top_end = max(1, int(round(height * 0.30)))
    mid_start = min(height - 1, int(round(height * 0.35)))
    mid_end = max(mid_start + 1, int(round(height * 0.70)))
    mid_end = min(height, mid_end)
    top_span = _mean_nonzero(spans[:top_end])
    mid_span = _mean_nonzero(spans[mid_start:mid_end])
    top_to_mid = top_span / mid_span if mid_span > 0 else 0.0
    return (3.0 * height / width), top_to_mid


def _classify_stack_state(
    height_score: float,
    top_to_mid_span_ratio: float,
) -> str:
    # Two independent stacked signatures are accepted:
    # 1) a very tall 3+1 group with a still-narrower upper band; or
    # 2) moderate vertical excess with a strongly collapsed upper lobe.
    # The first covers reviewed added-Kong geometry; the second covers the
    # larger player-side tilted stack seen in current target-room captures.
    if (
        height_score >= _STACKED_STRONG_HEIGHT_SCORE
        and top_to_mid_span_ratio <= _STACKED_STRONG_HEIGHT_MAX_TOP_TO_MID
    ) or (
        height_score >= _STACKED_MIN_HEIGHT_SCORE
        and top_to_mid_span_ratio <= _STACKED_MAX_TOP_TO_MID
    ):
        return STACKED
    if (
        height_score <= _FLAT_MAX_HEIGHT_SCORE
        and top_to_mid_span_ratio >= _FLAT_MIN_TOP_TO_MID
    ):
        return FLAT
    return UNKNOWN


def normalize_public_meld_crop(
    image: Any,
    group: PublicGeometryCandidate,
    *,
    canonical_height: int = _CANONICAL_HEIGHT,
) -> NormalizedPublicMeld:
    """Deskew and scale one already-detected public meld group.

    The normalized crop preserves aspect ratio. Stack detection is tri-state:
    strong flat geometry -> FLAT, strong 3+1 vertical excess plus upper-lobe
    collapse -> STACKED, and everything else -> UNKNOWN. UNKNOWN is
    intentional and must not be converted into a Mahjong action.
    """
    if canonical_height < 32:
        raise ValueError("canonical_height must be at least 32")
    if group.geometry_kind not in {"bottom_group", "top_group"}:
        return NormalizedPublicMeld(image=None, analysis=_unknown("not_meld_group"))

    x, y, width, height = group.pixel_bbox
    if width <= 0 or height <= 0:
        return NormalizedPublicMeld(
            image=None, analysis=_unknown("invalid_group_bbox")
        )

    try:
        import cv2
        import numpy as np
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - optional Vision dependency
        raise RuntimeError(
            "public meld normalization requires Pillow/OpenCV/numpy"
        ) from exc

    rgb = np.asarray(image.convert("RGB"))
    frame_height, frame_width = rgb.shape[:2]
    left = max(0, x)
    top = max(0, y)
    right = min(frame_width, x + width)
    bottom = min(frame_height, y + height)
    if right <= left or bottom <= top:
        return NormalizedPublicMeld(
            image=None, analysis=_unknown("group_bbox_outside_image")
        )

    crop = rgb[top:bottom, left:right]
    hsv = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)
    mask = (
        (hsv[:, :, 1] < 110)
        & (hsv[:, :, 2] > 110)
    ).astype(np.uint8) * 255
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        np.ones((3, 3), np.uint8),
        iterations=1,
    )

    ys, xs = np.nonzero(mask)
    if len(xs) < 40:
        return NormalizedPublicMeld(
            image=None, analysis=_unknown("insufficient_bright_face_geometry")
        )

    points = np.column_stack((xs, ys)).astype(np.float32)
    angle = _row_angle(cv2.minAreaRect(points))
    center = (crop.shape[1] / 2.0, crop.shape[0] / 2.0)
    matrix = cv2.getRotationMatrix2D(center, -angle, 1.0)
    rotated_rgb = cv2.warpAffine(
        crop,
        matrix,
        (crop.shape[1], crop.shape[0]),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
    rotated_mask = cv2.warpAffine(
        mask,
        matrix,
        (mask.shape[1], mask.shape[0]),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )

    ys, xs = np.nonzero(rotated_mask)
    if len(xs) < 40:
        return NormalizedPublicMeld(
            image=None, analysis=_unknown("deskew_removed_face_geometry")
        )

    tight_left = int(xs.min())
    tight_top = int(ys.min())
    tight_right = int(xs.max()) + 1
    tight_bottom = int(ys.max()) + 1
    tight_width = tight_right - tight_left
    tight_height = tight_bottom - tight_top
    if tight_width < 24 or tight_height < 20:
        return NormalizedPublicMeld(
            image=None, analysis=_unknown("tight_group_too_small")
        )

    tight_mask = rotated_mask[
        tight_top:tight_bottom,
        tight_left:tight_right,
    ]
    height_score, top_to_mid = _stack_features(tight_mask)
    stack_state = _classify_stack_state(height_score, top_to_mid)

    normalized_width = max(
        1, int(round(tight_width * canonical_height / tight_height))
    )
    tight_rgb = rotated_rgb[
        tight_top:tight_bottom,
        tight_left:tight_right,
    ]
    normalized_rgb = cv2.resize(
        tight_rgb,
        (normalized_width, canonical_height),
        interpolation=(
            cv2.INTER_AREA
            if canonical_height <= tight_height
            else cv2.INTER_CUBIC
        ),
    )

    issues = ["geometry_normalized"]
    if abs(angle) > 0.75:
        issues.append("row_deskew_applied")
    if stack_state == FLAT:
        issues.append("flat_three_face_geometry")
    elif stack_state == STACKED:
        issues.append("stacked_3_plus_1_geometry_candidate")
    else:
        issues.append("ambiguous_stack_geometry")

    analysis = PublicMeldGeometryAnalysis(
        rotation_degrees=round(angle, 4),
        stack_state=stack_state,
        height_score=round(height_score, 6),
        top_to_mid_span_ratio=round(top_to_mid, 6),
        normalized_size=(normalized_width, canonical_height),
        tight_bbox_in_group=(
            tight_left,
            tight_top,
            tight_width,
            tight_height,
        ),
        issues=tuple(issues),
    )
    return NormalizedPublicMeld(
        image=Image.fromarray(normalized_rgb),
        analysis=analysis,
    )



def find_flat_meld_seams(
    normalized: NormalizedPublicMeld,
) -> tuple[int, int] | None:
    """Find two geometry-only separators for a normalized FLAT three-face row.

    Search is deliberately local around the expected thirds.  A separator is
    accepted only when the bright-face column occupancy has a clear local
    valley relative to both neighboring shoulders.  Identity labels and SIFT
    scores never participate.  Ambiguous geometry returns None so callers can
    fail closed or retain the frozen equal-third diagnostic path.
    """
    if normalized.image is None or normalized.analysis.stack_state != FLAT:
        return None

    import cv2
    import numpy as np

    rgb = np.asarray(normalized.image.convert("RGB"))
    height, width = rgb.shape[:2]
    if width < 60 or height < 32:
        return None
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    mask = ((hsv[:, :, 1] < 110) & (hsv[:, :, 2] > 110)).astype(np.float32)
    occupancy = mask.mean(axis=0)
    # Smooth only enough to suppress glyph-scale single-column noise.
    occupancy = np.convolve(occupancy, np.ones(5, dtype=np.float32) / 5.0, mode="same")

    seams = []
    radius = max(3, int(round(width * 0.07)))
    shoulder = max(3, int(round(width * 0.05)))
    for fraction in (1.0 / 3.0, 2.0 / 3.0):
        center = int(round(width * fraction))
        lo = max(shoulder, center - radius)
        hi = min(width - shoulder - 1, center + radius)
        if hi <= lo:
            return None
        local = occupancy[lo : hi + 1]
        seam = lo + int(np.argmin(local))
        left_level = float(occupancy[max(0, seam - shoulder) : seam].mean())
        right_level = float(occupancy[seam + 1 : min(width, seam + 1 + shoulder)].mean())
        valley = float(occupancy[seam])
        # Require a visible valley on both sides; this is intentionally strict.
        if min(left_level, right_level) - valley < 0.10:
            return None
        seams.append(seam)

    first, second = seams
    widths = (first, second - first, width - second)
    expected = width / 3.0
    if any(part < expected * 0.72 or part > expected * 1.28 for part in widths):
        return None
    return first, second


def split_flat_meld_faces_by_seams(
    normalized: NormalizedPublicMeld,
) -> tuple[Any, ...]:
    """Conservatively split a FLAT row only when two automatic seams exist."""
    seams = find_flat_meld_seams(normalized)
    if seams is None or normalized.image is None:
        return ()
    first, second = seams
    width, height = normalized.image.size
    boundaries = (0, first, second, width)
    return tuple(
        normalized.image.crop((boundaries[i], 0, boundaries[i + 1], height))
        for i in range(3)
    )

def split_flat_meld_faces(
    normalized: NormalizedPublicMeld,
) -> tuple[Any, ...]:
    """Split a normalized FLAT row into three classifier-ready face crops.

    Stacked/ambiguous layouts intentionally return no faces here. The fourth
    overlaid face in a Kong needs its own reviewed stack-specific splitter;
    this function must not fabricate it from equal thirds.
    """
    if normalized.image is None or normalized.analysis.stack_state != FLAT:
        return ()

    width, height = normalized.image.size
    boundaries = (
        0,
        int(round(width / 3.0)),
        int(round(2.0 * width / 3.0)),
        width,
    )
    faces = []
    for index in range(3):
        left = boundaries[index]
        right = boundaries[index + 1]
        if right <= left:
            return ()
        faces.append(normalized.image.crop((left, 0, right, height)))
    return tuple(faces)
