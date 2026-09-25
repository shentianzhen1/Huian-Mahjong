"""Issue #69: conservative face segmentation for regular exposed meld groups.

This module accepts an already-detected public bottom_group and exposes
individual geometry-only face slots when the group looks like a regular
three-face row. It does not infer tile identity, actor intent, CHI/PENG/KONG,
or hidden/overlapped faces.

Stacked/added-Kong layouts are intentionally rejected until separately
reviewed geometry exists.
"""
from __future__ import annotations

from dataclasses import dataclass

from workspace.vision.public_tile_detector import PublicGeometryCandidate


@dataclass(frozen=True)
class PublicMeldFaceCandidate:
    pixel_bbox: tuple[int, int, int, int]
    normalized_bbox: tuple[float, float, float, float]
    confidence: float
    face_index: int

    def to_dict(self) -> dict:
        return {
            "pixel_bbox": list(self.pixel_bbox),
            "normalized_bbox": list(self.normalized_bbox),
            "confidence": self.confidence,
            "face_index": self.face_index,
            "tile_id": "UNKNOWN",
            "evidence_grade": "UNKNOWN",
        }


@dataclass(frozen=True)
class PublicMeldFaceSegmentation:
    faces: tuple[PublicMeldFaceCandidate, ...]
    issues: tuple[str, ...]
    source_bbox: tuple[float, float, float, float]

    def to_dict(self) -> dict:
        return {
            "schema_version": "public_meld_face_segmentation_v0_1",
            "faces": [face.to_dict() for face in self.faces],
            "issues": list(self.issues),
            "source_bbox": list(self.source_bbox),
            "regular_three_face_row": len(self.faces) == 3,
            "safe_for_runtime_identity": False,
            "safe_for_hint": False,
            "safe_for_executor": False,
        }


def _normalized(
    bbox: tuple[int, int, int, int],
    image_size: tuple[int, int],
) -> tuple[float, float, float, float]:
    image_width, image_height = image_size
    x, y, width, height = bbox
    return (
        round(x / image_width, 6),
        round(y / image_height, 6),
        round(width / image_width, 6),
        round(height / image_height, 6),
    )


def segment_regular_meld_faces(
    group: PublicGeometryCandidate,
    image_size: tuple[int, int],
) -> PublicMeldFaceSegmentation:
    """Split only a regular horizontal three-face public meld row.

    The gate is pixel-aspect based so it works across the two currently
    reviewed resolutions. It deliberately does not try to split 3+1 stacked
    Kong geometry. Any rejected group remains useful as group-level geometry,
    but contributes zero face identities.
    """
    image_width, image_height = image_size
    if image_width <= 0 or image_height <= 0:
        raise ValueError("image_size must be positive")

    if group.geometry_kind != "bottom_group":
        return PublicMeldFaceSegmentation(
            (), ("not_bottom_group",), group.normalized_bbox
        )

    x, y, width, height = group.pixel_bbox
    if width <= 0 or height <= 0:
        return PublicMeldFaceSegmentation(
            (), ("invalid_group_bbox",), group.normalized_bbox
        )

    # Previously reviewed eight-hand footage contains adjacent FOUR-face rows
    # whose width/height (~2.39) passed the old 0.82 three-face threshold.
    # Fail closed until pixels/independent separators support a true face count.
    implied_face_aspect = (width / 3.0) / height
    if not 0.50 <= implied_face_aspect <= 0.72:
        return PublicMeldFaceSegmentation(
            (),
            (
                "non_regular_three_face_geometry",
                f"implied_face_aspect={implied_face_aspect:.4f}",
            ),
            group.normalized_bbox,
        )

    if width < 30 or height < 24:
        return PublicMeldFaceSegmentation(
            (), ("group_too_small_for_face_split",), group.normalized_bbox
        )

    boundaries = [
        x,
        int(round(x + width / 3.0)),
        int(round(x + 2.0 * width / 3.0)),
        x + width,
    ]
    faces: list[PublicMeldFaceCandidate] = []
    for index in range(3):
        left = boundaries[index]
        right = boundaries[index + 1]
        if right <= left:
            return PublicMeldFaceSegmentation(
                (), ("degenerate_face_split",), group.normalized_bbox
            )
        bbox = (left, y, right - left, height)
        faces.append(
            PublicMeldFaceCandidate(
                pixel_bbox=bbox,
                normalized_bbox=_normalized(bbox, image_size),
                confidence=round(min(group.confidence, 0.82), 6),
                face_index=index,
            )
        )

    return PublicMeldFaceSegmentation(
        tuple(faces),
        ("geometry_only_regular_three_face_split",),
        group.normalized_bbox,
    )
