"""Source-qualified, development-only public river geometry for Issue #69.

A reviewed recording's SHA, session, resolution, and screen-side zones must all
match. A blob spanning two river tiles is split *only* when a visible seam
separates two bright faces; a wide box alone never implies a new discard.
Neither this component nor its geometry output identifies a tile, turn, or
Mahjong action. Caller must honor actor_trust when constructing RiverSnapshot.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
from math import isfinite
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PIL import Image
    from numpy import ndarray
    from workspace.vision.public_tile_detector import PublicGeometryFrame

SCHEMA_VERSION = "source_river_geometry_v0_1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
ACTORS = frozenset({"player", "opponent"})
BBox = tuple[float, float, float, float]


def _bbox(value: Any) -> BBox:
    if not isinstance(value, (tuple, list)) or len(value) != 4:
        raise ValueError("river zone must contain four numeric values")
    try:
        x, y, width, height = (float(part) for part in value)
    except (ValueError, TypeError) as exc:
        raise ValueError("river zone must contain four numeric values") from exc
    if (not all(map(isfinite, (x, y, width, height)))
            or x < 0 or y < 0 or width <= 0 or height <= 0
            or x + width > 1.000001 or y + height > 1.000001):
        raise ValueError("river zone must be normalized inside the frame")
    return (x, y, width, height)


@dataclass(frozen=True)
class RiverZone:
    actor: str
    bbox: BBox
    single_width: tuple[float, float]
    single_height: tuple[float, float]

    def __post_init__(self) -> None:
        if self.actor not in ACTORS:
            raise ValueError("actor must be player or opponent")
        object.__setattr__(self, "bbox", _bbox(self.bbox))
        for name, span in (("width", self.single_width), ("height", self.single_height)):
            if (len(span) != 2 or not all(map(isfinite, span))
                    or not (0 < span[0] <= span[1] <= 1)):
                raise ValueError(f"invalid single-tile {name} range")

    def contains(self, box: BBox) -> bool:
        x, y, width, height = box
        zx, zy, zw, zh = self.bbox
        # Full containment excludes hand tiles and central zoom animations.
        return (x >= zx and y >= zy
                and x + width <= zx + zw + 1e-6
                and y + height <= zy + zh + 1e-6)

    def single(self, box: BBox) -> bool:
        return (self.single_width[0] <= box[2] <= self.single_width[1]
                and self.single_height[0] <= box[3] <= self.single_height[1])


@dataclass(frozen=True)
class RiverManifest:
    source_session: str
    source_sha256: str
    frame_size: tuple[int, int]
    zones: tuple[RiverZone, ...]
    development_only: bool
    excluded_from_formal_promotion: bool
    reviewed_frame_span: tuple[int, int] | None = None

    def __post_init__(self) -> None:
        if (not isinstance(self.source_session, str) or not self.source_session
                or not isinstance(self.source_sha256, str)
                or not _SHA256.fullmatch(self.source_sha256)):
            raise ValueError("exact source session and SHA256 required")
        if (len(self.frame_size) != 2
                or any(type(n) is not int or n <= 0 for n in self.frame_size)):
            raise ValueError("frame_size must be positive [width, height]")
        if self.reviewed_frame_span is not None:
            span = self.reviewed_frame_span
            if (len(span) != 2 or any(type(n) is not int for n in span)
                    or span[0] < 0 or span[1] < span[0]):
                raise ValueError("reviewed_frame_span must be increasing nonnegative frames")
        if len(self.zones) != 2 or {zone.actor for zone in self.zones} != ACTORS:
            raise ValueError("one reviewed river zone required per actor")
        if not self.development_only or not self.excluded_from_formal_promotion:
            raise ValueError("reviewed source is never an independent holdout")
        first, second = (zone.bbox for zone in self.zones)
        overlap_x = max(0.0, min(first[0] + first[2], second[0] + second[2])
                        - max(first[0], second[0]))
        overlap_y = max(0.0, min(first[1] + first[3], second[1] + second[3])
                        - max(first[1], second[1]))
        if overlap_x * overlap_y > 0:
            raise ValueError("opponent and player river zones must not overlap")

    def zone(self, actor: str) -> RiverZone:
        return next(zone for zone in self.zones if zone.actor == actor)


def load_river_manifest(path: str | Path) -> RiverManifest:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported river geometry manifest")
    zones = tuple(RiverZone(
        actor=entry["actor"],
        bbox=_bbox(entry["bbox"]),
        single_width=tuple(float(v) for v in entry["single_width"]),
        single_height=tuple(float(v) for v in entry["single_height"]),
    ) for entry in data["zones"])
    return RiverManifest(
        source_session=data["source_session"],
        source_sha256=data["source_sha256"],
        frame_size=tuple(data["frame_size"]),
        zones=zones,
        development_only=data.get("development_only") is True,
        excluded_from_formal_promotion=data.get("excluded_from_formal_promotion") is True,
        reviewed_frame_span=(tuple(data["reviewed_frame_span"])
                             if "reviewed_frame_span" in data else None),
    )


@dataclass(frozen=True)
class QualifiedRiverFrame:
    """filtered_frame contains candidates; actor_trust gates downstream snapshots."""

    filtered_frame: PublicGeometryFrame
    actor_trust: dict[str, bool]
    issues: tuple[str, ...]


def _visible_two_face_seam(image_rgb: ndarray, box: tuple[int, int, int, int],
                           zone: RiverZone) -> int | None:
    """Require a visible dark inter-face seam between two bright upper halves.

    The width range only bounds the search. It is never sufficient to split.
    A glyph stroke or broad face shading must not be mistaken for a seam.
    """
    import cv2
    import numpy as np

    x, y, width, height = box
    min_w, max_w = zone.single_width
    frame_width = image_rgb.shape[1]
    if not min_w * frame_width * 1.65 <= width <= max_w * frame_width * 2.2:
        return None
    face = image_rgb[y:y + max(2, round(height * 0.48)), x:x + width]
    if face.shape[0] < 5 or face.shape[1] < 12:
        return None
    hsv = cv2.cvtColor(face, cv2.COLOR_RGB2HSV)
    brightness = hsv[:, :, 2].astype(np.float32).mean(axis=0) / 255
    low = max(3, round(width * 0.40))
    high = min(width - 3, round(width * 0.60))
    candidates = []
    for seam in range(low, high + 1):
        left = float(np.median(brightness[max(2, seam - 4):max(3, seam - 1)]))
        right = float(np.median(brightness[min(width - 3, seam + 2):min(width - 1, seam + 5)]))
        darkness = float(brightness[seam])
        if not (min_w * frame_width * .90 <= seam <= max_w * frame_width * 1.08
                and min_w * frame_width * .90 <= width - seam <= max_w * frame_width * 1.08):
            continue
        if min(left, right) < .66 or min(left, right) - darkness < .085:
            continue
        if (brightness[seam - 2:seam].mean() < .57
                or brightness[seam + 1:seam + 3].mean() < .57):
            continue
        candidates.append((min(left, right) - darkness, seam))
    if not candidates:
        return None
    return max(candidates)[1]


def qualify_river_frame(image: Image.Image, frame: PublicGeometryFrame,
                        *, manifest: RiverManifest,
                        actual_sha256: str) -> QualifiedRiverFrame:
    """Filter detector output without reading truth, classifying actions or tiles."""
    import numpy as np

    if (actual_sha256 != manifest.source_sha256
            or frame.session != manifest.source_session):
        raise ValueError("river source session/hash mismatch")
    if image.size != manifest.frame_size:
        raise ValueError("river frame resolution mismatch")
    if manifest.reviewed_frame_span is not None and (
        type(frame.frame) is not int
        or not manifest.reviewed_frame_span[0] <= frame.frame <= manifest.reviewed_frame_span[1]
    ):
        raise ValueError("frame outside source-reviewed river interval")

    rgb = np.asarray(image.convert("RGB"))
    by_actor: dict[str, list[Any]] = {zone.actor: [] for zone in manifest.zones}
    trusted = {zone.actor: True for zone in manifest.zones}
    issues: list[str] = []
    for candidate in frame.candidates:
        # Existing detector calls touching faces a single_face until separated.
        # Upper-protrusion art and bottom_group must not become river facts.
        if candidate.geometry_kind != "single_face":
            continue
        matched_zones = [zone for zone in manifest.zones
                         if zone.contains(candidate.normalized_bbox)]
        if len(matched_zones) > 1:
            raise ValueError("ambiguous overlapping river zones")
        if not matched_zones:
            continue
        zone = matched_zones[0]
        if not zone.single_height[0] <= candidate.normalized_bbox[3] <= zone.single_height[1]:
            continue
        if zone.single(candidate.normalized_bbox):
            by_actor[zone.actor].append(candidate)
            continue
        x, y, width, height = candidate.pixel_bbox
        if width < zone.single_width[0] * manifest.frame_size[0] * 1.55:
            # Tiny non-tile components are not public river observations.
            continue
        seam = _visible_two_face_seam(rgb, (x, y, width, height), zone)
        if seam is None:
            trusted[zone.actor] = False
            issues.append(f"{zone.actor}:unsplit_wide_river_component")
            continue
        for raw in ((x, y, seam, height), (x + seam, y, width - seam, height)):
            px, py, pw, ph = raw
            normalized = (round(px / manifest.frame_size[0], 6),
                          round(py / manifest.frame_size[1], 6),
                          round(pw / manifest.frame_size[0], 6),
                          round(ph / manifest.frame_size[1], 6))
            by_actor[zone.actor].append(replace(
                candidate, pixel_bbox=raw, normalized_bbox=normalized,
                geometry_kind="river_split_face",
            ))
        issues.append(f"{zone.actor}:visible_two_face_seam")

    # Never stream a partial actor river when an unresolved blob is present.
    kept = tuple(candidate for zone in manifest.zones if trusted[zone.actor]
                 for candidate in by_actor[zone.actor])
    return QualifiedRiverFrame(
        filtered_frame=replace(frame, candidates=kept,
                               issues=tuple(frame.issues) + tuple(issues)),
        actor_trust=trusted,
        issues=tuple(issues),
    )
