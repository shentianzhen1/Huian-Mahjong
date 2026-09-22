"""Development Public Tile Detector V0.1.

This detector is deliberately geometry-first.  It finds tile-like public UI
candidates across the frame but does not decide Mahjong actions, actors, river
order, or tile identity.  Stable River/Meld observers and the Action Assembler
own those semantics.

The first calibration set is already-reviewed development evidence and remains
excluded from formal Runtime Vision promotion.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import cv2
import numpy as np
from PIL import Image


@dataclass(frozen=True)
class PublicGeometryCandidate:
    pixel_bbox: tuple[int, int, int, int]
    normalized_bbox: tuple[float, float, float, float]
    geometry_kind: str
    confidence: float
    fill_ratio: float
    frame: str | int | None
    session: str | None

    def to_dict(self) -> dict:
        return {
            "pixel_bbox": list(self.pixel_bbox),
            "normalized_bbox": list(self.normalized_bbox),
            "geometry_kind": self.geometry_kind,
            "confidence": self.confidence,
            "fill_ratio": self.fill_ratio,
            "frame": self.frame,
            "session": self.session,
            "tile_id": "UNKNOWN",
        }


@dataclass(frozen=True)
class PublicGeometryFrame:
    candidates: tuple[PublicGeometryCandidate, ...]
    issues: tuple[str, ...]
    frame: str | int | None
    session: str | None

    def to_dict(self) -> dict:
        return {
            "schema_version": "public_tile_detector_v0_1",
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "issues": list(self.issues),
            "frame": self.frame,
            "session": self.session,
            "safe_for_hint": False,
            "safe_for_executor": False,
        }


def _normalized(
    bbox: tuple[int, int, int, int],
    width: int,
    height: int,
) -> tuple[float, float, float, float]:
    x, y, box_width, box_height = bbox
    return (
        round(x / width, 6),
        round(y / height, 6),
        round(box_width / width, 6),
        round(box_height / height, 6),
    )


def _dense_segments(values: np.ndarray, threshold: float) -> list[tuple[int, int]]:
    selected = values >= threshold
    segments: list[tuple[int, int]] = []
    start: int | None = None
    for index, value in enumerate(selected):
        if bool(value) and start is None:
            start = index
        if start is not None and (
            not bool(value) or index == len(selected) - 1
        ):
            end = index if bool(value) and index == len(selected) - 1 else index - 1
            segments.append((start, end))
            start = None
    return segments


def _intersection(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    x1 = max(first[0], second[0])
    y1 = max(first[1], second[1])
    x2 = min(first[0] + first[2], second[0] + second[2])
    y2 = min(first[1] + first[3], second[1] + second[3])
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def target_coverage(
    candidate_bbox: tuple[float, float, float, float],
    target_bbox: tuple[float, float, float, float],
) -> float:
    """Fraction of a reviewed target bbox covered by one detector candidate."""
    target_area = target_bbox[2] * target_bbox[3]
    if target_area <= 0:
        raise ValueError("target bbox must have positive area")
    return _intersection(candidate_bbox, target_bbox) / target_area


def best_target_coverage(
    detection: PublicGeometryFrame,
    target_bbox: tuple[float, float, float, float],
) -> tuple[float, PublicGeometryCandidate | None]:
    best_score = 0.0
    best_candidate: PublicGeometryCandidate | None = None
    for candidate in detection.candidates:
        score = target_coverage(candidate.normalized_bbox, target_bbox)
        if score > best_score:
            best_score = score
            best_candidate = candidate
    return best_score, best_candidate


def _expand_bottom_group(
    bbox: tuple[int, int, int, int],
    frame_width: int,
    frame_height: int,
) -> tuple[int, int, int, int]:
    """Restore visible tile borders that the low-saturation mask trims.

    The padding is scale-relative and does not encode a target count, group
    index, or absolute x position.
    """
    x, y, width, height = bbox
    pad_x = max(2, int(round(frame_width * 0.002)))
    pad_top = max(4, int(round(frame_height * 0.025)))
    pad_bottom = max(3, int(round(frame_height * 0.0125)))
    left = max(0, x - pad_x)
    top = max(0, y - pad_top)
    right = min(frame_width, x + width + pad_x)
    bottom = min(frame_height, y + height + pad_bottom)
    return left, top, right - left, bottom - top


def _upper_protrusions(
    mask: np.ndarray,
    bbox: tuple[int, int, int, int],
    frame_width: int,
    frame_height: int,
) -> list[tuple[int, int, int, int, float]]:
    """Recover a large offered/public tile merged into a smaller tile row.

    In reviewed target-room response frames, the enlarged public tile may touch
    the row below in the brightness mask.  Instead of assigning an absolute
    ROI, find a strong horizontal occupancy jump, then recover dense vertical
    segments in the upper lobe.

    The same logic is purely relational and simply yields no candidate when
    the signature is absent.
    """
    x, y, width, height = bbox
    patch = mask[y : y + height, x : x + width]
    if patch.shape[0] < 10 or patch.shape[1] < 10:
        return []

    rows = patch.sum(axis=1).astype(float)
    low = max(2, int(round(len(rows) * 0.15)))
    high = max(low + 1, int(round(len(rows) * 0.80)))
    jumps = rows[1:] - rows[:-1]
    if high <= low or len(jumps[low:high]) == 0:
        return []

    jump_index = low + int(np.argmax(jumps[low:high]))
    jump = float(jumps[jump_index])
    if jump <= max(10.0, width * 0.25):
        return []

    upper = patch[: jump_index + 2]
    columns = upper.sum(axis=0)
    threshold = max(5.0, upper.shape[0] * 0.25)
    results: list[tuple[int, int, int, int, float]] = []
    for start, end in _dense_segments(columns, threshold):
        segment_width = end - start + 1
        if not (
            frame_width * 0.015
            <= segment_width
            <= frame_width * 0.085
        ):
            continue
        segment = upper[:, start : end + 1]
        ys, xs = np.nonzero(segment)
        if len(xs) < 20:
            continue

        left = x + start + int(xs.min())
        top = y + int(ys.min())
        right = x + start + int(xs.max()) + 1
        bottom = y + int(ys.max()) + 1

        pad_x = 3
        pad_top = 5
        pad_bottom = 13
        left = max(0, left - pad_x)
        top = max(0, top - pad_top)
        right = min(frame_width, right + pad_x)
        bottom = min(frame_height, bottom + pad_bottom)

        candidate_bbox = (left, top, right - left, bottom - top)
        local = mask[top:bottom, left:right]
        fill_ratio = float(local.mean()) if local.size else 0.0
        results.append((*candidate_bbox, fill_ratio))
    return results


def _dedupe(
    candidates: Iterable[PublicGeometryCandidate],
) -> tuple[PublicGeometryCandidate, ...]:
    ordered = sorted(
        candidates,
        key=lambda item: (
            -item.confidence,
            -(item.normalized_bbox[2] * item.normalized_bbox[3]),
        ),
    )
    kept: list[PublicGeometryCandidate] = []
    for candidate in ordered:
        area = candidate.normalized_bbox[2] * candidate.normalized_bbox[3]
        duplicate = False
        for accepted in kept:
            accepted_area = accepted.normalized_bbox[2] * accepted.normalized_bbox[3]
            intersection = _intersection(
                candidate.normalized_bbox,
                accepted.normalized_bbox,
            )
            union = area + accepted_area - intersection
            iou = intersection / union if union > 0 else 0.0
            if iou >= 0.88:
                duplicate = True
                break
        if not duplicate:
            kept.append(candidate)
    return tuple(
        sorted(
            kept,
            key=lambda item: (
                item.pixel_bbox[1],
                item.pixel_bbox[0],
                item.geometry_kind,
            ),
        )
    )


def detect_public_tile_geometry(
    image: Image.Image,
    *,
    frame: str | int | None = None,
    session: str | None = None,
) -> PublicGeometryFrame:
    """Return public tile-like geometry candidates without semantic promotion.

    V0.1 uses a low-saturation bright-face mask because reviewed target-room
    public tiles have a pale tile body while retaining red/green artwork.
    Candidate intake is intentionally broad; temporal observers are responsible
    for deciding whether a stable new candidate is a discard/meld change.
    """
    rgb = np.asarray(image.convert("RGB"))
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    height, width = bgr.shape[:2]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    mask = (
        (hsv[:, :, 1] < 105)
        & (hsv[:, :, 2] > 115)
    ).astype(np.uint8)
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        np.ones((3, 3), np.uint8),
        iterations=1,
    )

    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    candidates: list[PublicGeometryCandidate] = []
    oversized_seen = 0

    for x, y, box_width, box_height, area in stats[1:count]:
        x, y, box_width, box_height, area = map(
            int, (x, y, box_width, box_height, area)
        )
        if box_width <= 0 or box_height <= 0:
            continue

        normalized_width = box_width / width
        normalized_height = box_height / height
        fill_ratio = area / (box_width * box_height)

        if not (0.012 <= normalized_width <= 0.25):
            continue
        if not (0.04 <= normalized_height <= 0.26):
            continue
        if fill_ratio < 0.18:
            continue

        raw_bbox = (x, y, box_width, box_height)

        if normalized_width <= 0.085:
            confidence = min(0.82, 0.48 + fill_ratio * 0.40)
            candidates.append(
                PublicGeometryCandidate(
                    raw_bbox,
                    _normalized(raw_bbox, width, height),
                    "single_face",
                    round(confidence, 6),
                    round(fill_ratio, 6),
                    frame,
                    session,
                )
            )
            continue

        oversized_seen += 1

        # A compact bottom-row wide component can represent a visible public
        # meld group.  This is still only a geometry candidate.
        if y > height * 0.72 and normalized_width <= 0.18:
            group_bbox = _expand_bottom_group(raw_bbox, width, height)
            local = mask[
                group_bbox[1] : group_bbox[1] + group_bbox[3],
                group_bbox[0] : group_bbox[0] + group_bbox[2],
            ]
            group_fill = float(local.mean()) if local.size else 0.0
            candidates.append(
                PublicGeometryCandidate(
                    group_bbox,
                    _normalized(group_bbox, width, height),
                    "bottom_group",
                    round(min(0.86, 0.58 + group_fill * 0.36), 6),
                    round(group_fill, 6),
                    frame,
                    session,
                )
            )

        for left, top, candidate_width, candidate_height, protrusion_fill in (
            _upper_protrusions(mask, raw_bbox, width, height)
        ):
            candidate_bbox = (
                left,
                top,
                candidate_width,
                candidate_height,
            )
            candidates.append(
                PublicGeometryCandidate(
                    candidate_bbox,
                    _normalized(candidate_bbox, width, height),
                    "upper_protrusion",
                    round(
                        min(0.90, 0.68 + protrusion_fill * 0.28),
                        6,
                    ),
                    round(protrusion_fill, 6),
                    frame,
                    session,
                )
            )

    deduped = _dedupe(candidates)
    issues = ["candidate_intake_only"]
    if oversized_seen:
        issues.append(f"oversized_components={oversized_seen}")
    if not deduped:
        issues.append("no_public_geometry_candidates")

    return PublicGeometryFrame(
        candidates=deduped,
        issues=tuple(issues),
        frame=frame,
        session=session,
    )
