"""Development-only opponent exposed-meld domain transfer.

Player and opponent exposed melds already share the same geometry normalizer.
The remaining opponent-specific domain gap is expected to be dominated by
source-resolution loss: the opponent's tile is rendered smaller before the
existing public-meld normalizer enlarges it to the classifier's canonical size.

This module therefore models only:
    canonical tile -> measured small source face -> canonical tile

No angle, perspective, blur, JPEG loss or random jitter is invented here.
Those may be added only after real top_group measurements support them.

The profile is intentionally PENDING until a source-verified, settled opponent
top_group produces exactly three classifier-ready faces. Runtime/Hint/Executor
must not consume this module.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


PROFILE_SCHEMA = "opponent_meld_domain_profile_v0_1"
PENDING = "PENDING_REAL_TOP_GROUP_MEASUREMENT"
MEASURED = "MEASURED_REAL_TOP_GROUP"
CANONICAL_FACE_SIZE = (56, 96)


@dataclass(frozen=True)
class OpponentMeldDomainProfile:
    status: str
    canonical_face_size: tuple[int, int]
    measured_source_face_size_px: tuple[int, int] | None
    measurement_source_review_id: str | None

    @property
    def ready(self) -> bool:
        return (
            self.status == MEASURED
            and self.measured_source_face_size_px is not None
        )


def load_opponent_meld_domain_profile(
    path: str | Path,
) -> OpponentMeldDomainProfile:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != PROFILE_SCHEMA:
        raise ValueError("expected opponent meld domain profile")

    canonical = payload.get("canonical_classifier_face_size")
    if (
        not isinstance(canonical, list)
        or len(canonical) != 2
        or not all(isinstance(value, int) and not isinstance(value, bool) for value in canonical)
    ):
        raise ValueError("canonical classifier face size must be two integers")
    canonical_size = (canonical[0], canonical[1])
    if canonical_size != CANONICAL_FACE_SIZE:
        raise ValueError("opponent domain profile canonical size drifted")

    raw_measured = payload.get("measured_source_face_size_px")
    measured: tuple[int, int] | None
    if raw_measured is None:
        measured = None
    elif (
        isinstance(raw_measured, list)
        and len(raw_measured) == 2
        and all(
            isinstance(value, int) and not isinstance(value, bool) and value > 0
            for value in raw_measured
        )
    ):
        measured = (raw_measured[0], raw_measured[1])
    else:
        raise ValueError("measured source face size must be null or two positive integers")

    status = payload.get("status")
    if status not in {PENDING, MEASURED}:
        raise ValueError("unsupported opponent meld domain profile status")
    review_id = payload.get("measurement_source_review_id")
    if review_id is not None and (
        not isinstance(review_id, str) or not review_id.strip()
    ):
        raise ValueError("measurement source review id must be null or nonblank")

    if status == PENDING:
        if measured is not None or review_id is not None:
            raise ValueError("pending profile cannot contain measured dimensions")
    else:
        if measured is None or review_id is None:
            raise ValueError("measured profile requires dimensions and review id")
        width, height = measured
        canonical_width, canonical_height = canonical_size
        if width >= canonical_width or height >= canonical_height:
            raise ValueError(
                "opponent source-loss profile must represent a smaller source face"
            )

    rendering = payload.get("rendering_policy")
    expected_rendering = {
        "downsample": "area",
        "restore_to_canonical": "bicubic",
        "extra_blur": False,
        "jpeg_recompression": False,
        "rotation_or_perspective": "none_here_existing_geometry_normalizer_handles_it",
        "random_jitter": False,
    }
    if rendering != expected_rendering:
        raise ValueError("opponent domain rendering policy drifted")

    for key in (
        "changes_runtime_behavior",
        "formal_promotion_evidence",
        "safe_for_runtime",
        "safe_for_hint",
        "safe_for_executor",
    ):
        if payload.get(key) is not False:
            raise ValueError(f"{key} must remain false")

    return OpponentMeldDomainProfile(
        status=status,
        canonical_face_size=canonical_size,
        measured_source_face_size_px=measured,
        measurement_source_review_id=review_id,
    )



def qualify_opponent_meld_domain_profile(
    profile: OpponentMeldDomainProfile,
    review_queue_payload: dict[str, Any],
) -> dict[str, Any]:
    """Require a classifier-ready, exact-source-verified queue item.

    A measured pixel size alone is not enough. The measurement must come from
    the locked opponent review queue after the corresponding settled top_group
    has passed the normalizer/splitter and its source bytes were exact-verified.
    """
    result = {
        "schema_version": "opponent_meld_domain_profile_qualification_v0_1",
        "qualified": False,
        "reason": "profile_pending_measurement",
        "measurement_source_review_id": profile.measurement_source_review_id,
        "changes_runtime_behavior": False,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }
    if not profile.ready or profile.measurement_source_review_id is None:
        return result

    items = review_queue_payload.get("items")
    if not isinstance(items, list):
        result["reason"] = "review_queue_missing_items"
        return result
    matches = [
        row
        for row in items
        if isinstance(row, dict)
        and row.get("review_id") == profile.measurement_source_review_id
    ]
    if len(matches) != 1:
        result["reason"] = "measurement_source_not_unique_in_review_queue"
        return result

    row = matches[0]
    verification = row.get("source_verification")
    if not (
        isinstance(verification, str)
        and verification.startswith("SHA256_EXACT_VERIFIED")
    ):
        result["reason"] = "measurement_source_not_exact_sha_verified"
        return result
    if row.get("crop_status") != "CLASSIFIER_READY":
        result["reason"] = "measurement_source_crop_not_classifier_ready"
        return result

    measured = row.get("measured_source_face_size_px")
    if (
        not isinstance(measured, list)
        or len(measured) != 2
        or tuple(measured) != profile.measured_source_face_size_px
    ):
        result["reason"] = "profile_dimensions_do_not_match_review_queue"
        return result

    result["qualified"] = True
    result["reason"] = "measured_source_exact_verified_and_classifier_ready"
    return result

def simulate_opponent_source_resolution_loss(
    image: Any,
    profile: OpponentMeldDomainProfile,
) -> Any:
    """Downsample to a measured opponent face then restore to canonical size.

    The caller must supply a MEASURED profile. A pending profile raises instead
    of silently inventing a pixel size.
    """
    if not profile.ready or profile.measured_source_face_size_px is None:
        raise ValueError("opponent meld domain profile is not measured")

    try:
        import cv2
        import numpy as np
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - optional Vision dependency
        raise RuntimeError(
            "opponent meld domain transfer requires Pillow/OpenCV/numpy"
        ) from exc

    canonical_width, canonical_height = profile.canonical_face_size
    source_width, source_height = profile.measured_source_face_size_px
    canonical = image.convert("RGB").resize(
        (canonical_width, canonical_height),
        Image.Resampling.BICUBIC,
    )
    rgb = np.asarray(canonical, dtype=np.uint8)
    small = cv2.resize(
        rgb,
        (source_width, source_height),
        interpolation=cv2.INTER_AREA,
    )
    restored = cv2.resize(
        small,
        (canonical_width, canonical_height),
        interpolation=cv2.INTER_CUBIC,
    )
    return Image.fromarray(restored)


def describe_opponent_domain_profile(
    profile: OpponentMeldDomainProfile,
) -> dict[str, Any]:
    return {
        "schema_version": "opponent_meld_domain_profile_status_v0_1",
        "status": profile.status,
        "ready": profile.ready,
        "canonical_face_size": list(profile.canonical_face_size),
        "measured_source_face_size_px": (
            list(profile.measured_source_face_size_px)
            if profile.measured_source_face_size_px is not None
            else None
        ),
        "measurement_source_review_id": profile.measurement_source_review_id,
        "changes_runtime_behavior": False,
        "formal_promotion_evidence": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }
