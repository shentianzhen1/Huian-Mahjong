"""Recover stable public-meld geometry near a reviewed private timestamp.

This is a local development utility for already-inspected material. It verifies
the exact source SHA first, scans a small time window with the repository's
geometry detector, keeps only regular 3-face meld groups, and clusters stable
bboxes. It NEVER assigns tile identities or action semantics.

Recovered pixels must still be compared against the private user-confirmed
review packet before becoming template-eligible.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

from workspace.vision.public_meld_private_recovery_queue import (
    RecoveryItem,
    qualify_recovered_item,
)
from workspace.vision.private_video_chunking import sha256_file


@dataclass(frozen=True)
class RecoveryObservation:
    frame: int
    timestamp_seconds: float
    geometry_kind: str
    normalized_bbox: tuple[float, float, float, float]
    confidence: float


@dataclass(frozen=True)
class RecoveryCluster:
    geometry_kind: str
    representative_bbox: tuple[float, float, float, float]
    first_frame: int
    last_frame: int
    first_timestamp_seconds: float
    last_timestamp_seconds: float
    observation_count: int
    mean_confidence: float
    representative_frame: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "geometry_kind": self.geometry_kind,
            "representative_bbox": list(self.representative_bbox),
            "frame_range": [self.first_frame, self.last_frame],
            "timestamp_range_seconds": [
                round(self.first_timestamp_seconds, 6),
                round(self.last_timestamp_seconds, 6),
            ],
            "observation_count": self.observation_count,
            "mean_confidence": round(self.mean_confidence, 6),
            "representative_frame": self.representative_frame,
            "tile_identity": "UNKNOWN",
            "action_kind": "UNKNOWN",
            "review_status": "pending_private_pixel_comparison",
            "formal_promotion_evidence": False,
            "safe_for_hint": False,
            "safe_for_executor": False,
        }


def bbox_iou(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    ax, ay, aw, ah = first
    bx, by, bw, bh = second
    if min(aw, ah, bw, bh) <= 0:
        raise ValueError("bbox dimensions must be positive")
    left = max(ax, bx)
    top = max(ay, by)
    right = min(ax + aw, bx + bw)
    bottom = min(ay + ah, by + bh)
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    union = aw * ah + bw * bh - intersection
    return intersection / union if union > 0 else 0.0


def cluster_recovery_observations(
    observations: tuple[RecoveryObservation, ...] | list[RecoveryObservation],
    *,
    minimum_observations: int = 3,
    minimum_iou: float = 0.80,
) -> tuple[RecoveryCluster, ...]:
    if isinstance(minimum_observations, bool) or not isinstance(minimum_observations, int) or minimum_observations < 1:
        raise ValueError("minimum_observations must be positive integer")
    if isinstance(minimum_iou, bool) or not isinstance(minimum_iou, (int, float)):
        raise ValueError("minimum_iou must be numeric")
    minimum_iou = float(minimum_iou)
    if not 0 < minimum_iou <= 1:
        raise ValueError("minimum_iou must be in (0, 1]")

    groups: list[list[RecoveryObservation]] = []
    for observation in sorted(
        observations,
        key=lambda row: (row.timestamp_seconds, row.frame, row.geometry_kind),
    ):
        if observation.geometry_kind not in {"bottom_group", "top_group"}:
            continue
        if (
            not math.isfinite(observation.timestamp_seconds)
            or observation.timestamp_seconds < 0
            or not 0 <= observation.confidence <= 1
        ):
            raise ValueError("invalid recovery observation")
        matches = [
            group
            for group in groups
            if group[-1].geometry_kind == observation.geometry_kind
            and bbox_iou(group[-1].normalized_bbox, observation.normalized_bbox) >= minimum_iou
        ]
        if matches:
            matches[0].append(observation)
        else:
            groups.append([observation])

    results: list[RecoveryCluster] = []
    for group in groups:
        if len(group) < minimum_observations:
            continue
        representative = max(
            group,
            key=lambda row: (row.confidence, -abs(row.timestamp_seconds - group[len(group)//2].timestamp_seconds)),
        )
        results.append(
            RecoveryCluster(
                geometry_kind=representative.geometry_kind,
                representative_bbox=representative.normalized_bbox,
                first_frame=min(row.frame for row in group),
                last_frame=max(row.frame for row in group),
                first_timestamp_seconds=min(row.timestamp_seconds for row in group),
                last_timestamp_seconds=max(row.timestamp_seconds for row in group),
                observation_count=len(group),
                mean_confidence=sum(row.confidence for row in group) / len(group),
                representative_frame=representative.frame,
            )
        )
    return tuple(
        sorted(
            results,
            key=lambda row: (-row.observation_count, -row.mean_confidence, row.geometry_kind),
        )
    )


def scan_recovery_window(
    video: str | Path,
    item: RecoveryItem,
    *,
    radius_seconds: float = 2.0,
    sample_stride_frames: int = 3,
    minimum_observations: int = 3,
) -> dict[str, Any]:
    """Scan one reviewed recovery window after exact source verification."""
    if isinstance(radius_seconds, bool) or not isinstance(radius_seconds, (int, float)):
        raise ValueError("radius_seconds must be numeric")
    radius_seconds = float(radius_seconds)
    if not math.isfinite(radius_seconds) or radius_seconds <= 0:
        raise ValueError("radius_seconds must be finite and positive")
    if isinstance(sample_stride_frames, bool) or not isinstance(sample_stride_frames, int) or sample_stride_frames < 1:
        raise ValueError("sample_stride_frames must be positive integer")

    path = Path(video)
    actual_sha = sha256_file(path)
    if actual_sha != item.source_sha256_from_repository_evidence:
        raise ValueError("source SHA mismatch; recovery aborted before decode")

    import cv2
    from PIL import Image
    from workspace.vision.public_meld_face_segmentation import prepare_public_meld_faces
    from workspace.vision.public_tile_detector import detect_public_tile_geometry

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError("source is not a decodable video")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if not math.isfinite(fps) or fps <= 0 or frame_count <= 0:
        capture.release()
        raise ValueError("source video metadata is invalid")

    first_frame = max(0, int(math.floor((item.timestamp_seconds - radius_seconds) * fps)))
    last_frame = min(
        frame_count - 1,
        int(math.ceil((item.timestamp_seconds + radius_seconds) * fps)),
    )
    observations: list[RecoveryObservation] = []
    try:
        for frame_index in range(first_frame, last_frame + 1, sample_stride_frames):
            if not capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index):
                raise ValueError("cannot seek recovery frame")
            ok, bgr = capture.read()
            if not ok:
                raise ValueError(f"missing recovery frame {frame_index}")
            timestamp = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(rgb)
            detection = detect_public_tile_geometry(
                image,
                frame=frame_index,
                session=item.recovery_id,
            )
            for candidate in detection.candidates:
                if candidate.geometry_kind not in {"bottom_group", "top_group"}:
                    continue
                prepared = prepare_public_meld_faces(image, candidate)
                if (
                    prepared.geometry.stack_state != "FLAT"
                    or len(prepared.face_images) != 3
                ):
                    continue
                observations.append(
                    RecoveryObservation(
                        frame=frame_index,
                        timestamp_seconds=timestamp,
                        geometry_kind=candidate.geometry_kind,
                        normalized_bbox=candidate.normalized_bbox,
                        confidence=float(candidate.confidence),
                    )
                )
    finally:
        capture.release()

    clusters = cluster_recovery_observations(
        observations,
        minimum_observations=minimum_observations,
    )
    return {
        "schema_version": "public_meld_private_recovery_scan_v0_1",
        "recovery_id": item.recovery_id,
        "source_sha256": actual_sha,
        "expected_tiles": list(item.expected_tiles),
        "window_seconds": [
            round(max(0.0, item.timestamp_seconds - radius_seconds), 6),
            round(item.timestamp_seconds + radius_seconds, 6),
        ],
        "sample_stride_frames": sample_stride_frames,
        "regular_group_observations": len(observations),
        "stable_clusters": [cluster.to_dict() for cluster in clusters],
        "tile_identity": "UNKNOWN",
        "action_kind": "UNKNOWN",
        "requires_private_pixel_comparison": True,
        "template_eligible": False,
        "holdout_eligible": False,
        "formal_promotion_evidence": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }
