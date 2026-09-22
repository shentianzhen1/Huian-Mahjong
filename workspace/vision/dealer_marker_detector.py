"""Development dealer-marker detector for the target-room UI.

The detector answers only one visual question: is the visible dealer marker
next to the local player anchor or the opponent anchor?

It does not OCR the dealer count ("庄3", "庄5"), derive dealer base, infer turn
order, or mutate any game/runtime state.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from workspace.vision.hand_context_assembler import DealerEvidence
from workspace.vision.tiles_v0_1.public_state import NormalizedBox


@dataclass(frozen=True)
class DealerMarkerProfile:
    """Two evidence-backed normalized search zones.

    These zones are adjacent to the same local-player/opponent avatar anchors
    already present in the target-room UI. They were reviewed across two real
    development sessions: 66fe863f (opponent dealer) and b3892b34 (player
    dealer). They are development calibration, not formal promotion evidence.
    """

    player_marker: NormalizedBox = NormalizedBox(0.115, 0.640, 0.170, 0.750)
    opponent_marker: NormalizedBox = NormalizedBox(0.655, 0.005, 0.695, 0.075)
    minimum_mask_ratio: float = 0.030
    minimum_component_ratio: float = 0.020

    def __post_init__(self) -> None:
        for name in ("minimum_mask_ratio", "minimum_component_ratio"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not 0 < float(value) < 1
            ):
                raise ValueError(f"{name} must be within (0, 1)")


@dataclass(frozen=True)
class MarkerSignal:
    mask_ratio: float
    largest_component_ratio: float
    active: bool

    def to_dict(self) -> dict:
        return {
            "mask_ratio": round(self.mask_ratio, 6),
            "largest_component_ratio": round(
                self.largest_component_ratio,
                6,
            ),
            "active": self.active,
        }


@dataclass(frozen=True)
class DealerMarkerObservation:
    actor: str | None
    confidence: float
    player_signal: MarkerSignal
    opponent_signal: MarkerSignal
    issues: tuple[str, ...]
    frame: str | int | None
    session: str | None
    evidence_refs: tuple[str, ...]
    safe_for_hint: bool = False
    safe_for_executor: bool = False

    def __post_init__(self) -> None:
        if self.actor not in {None, "player", "opponent"}:
            raise ValueError("actor must be player, opponent or None")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be within [0, 1]")

    def to_dict(self) -> dict:
        return {
            "schema_version": "dealer_marker_detector_v0_1",
            "actor": self.actor,
            "confidence": round(self.confidence, 6),
            "player_signal": self.player_signal.to_dict(),
            "opponent_signal": self.opponent_signal.to_dict(),
            "issues": list(self.issues),
            "frame": self.frame,
            "session": self.session,
            "evidence_refs": list(self.evidence_refs),
            "safe_for_hint": False,
            "safe_for_executor": False,
        }

    def to_dealer_evidence(
        self,
        *,
        timestamp_seconds: float,
        player_seat: int | None,
    ) -> DealerEvidence:
        if player_seat is not None and (
            type(player_seat) is not int or player_seat not in (0, 1)
        ):
            raise ValueError("player_seat must be seat 0, seat 1 or None")

        dealer_seat: int | None = None
        if self.actor is not None and player_seat is not None:
            dealer_seat = (
                player_seat
                if self.actor == "player"
                else 1 - player_seat
            )

        return DealerEvidence(
            timestamp_seconds=timestamp_seconds,
            dealer_seat=dealer_seat,
            confidence=self.confidence,
            evidence_refs=self.evidence_refs,
        )


def _orange_red_mask(rgb: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    hue, saturation, value = cv2.split(hsv)
    return (
        ((hue < 25) | (hue > 170))
        & (saturation > 120)
        & (value > 140)
    ).astype(np.uint8)


def _marker_signal(
    image: Image.Image,
    box: NormalizedBox,
    profile: DealerMarkerProfile,
) -> MarkerSignal:
    crop = np.asarray(box.crop(image.convert("RGB")))
    if crop.size == 0:
        return MarkerSignal(0.0, 0.0, False)

    mask = _orange_red_mask(crop)
    mask_ratio = float(mask.mean())

    count, _, stats, _ = cv2.connectedComponentsWithStats(
        (mask * 255).astype(np.uint8),
        8,
    )
    largest_area = max(
        (
            int(stats[index, cv2.CC_STAT_AREA])
            for index in range(1, count)
        ),
        default=0,
    )
    roi_area = mask.shape[0] * mask.shape[1]
    component_ratio = (
        largest_area / roi_area
        if roi_area > 0
        else 0.0
    )
    active = (
        mask_ratio >= profile.minimum_mask_ratio
        and component_ratio >= profile.minimum_component_ratio
    )
    return MarkerSignal(
        mask_ratio=mask_ratio,
        largest_component_ratio=component_ratio,
        active=active,
    )


def _confidence(
    active: MarkerSignal,
    inactive: MarkerSignal,
    profile: DealerMarkerProfile,
) -> float:
    # Geometry/color confidence only. This is not a recognition probability.
    mask_margin = max(
        0.0,
        active.mask_ratio - profile.minimum_mask_ratio,
    )
    component_margin = max(
        0.0,
        active.largest_component_ratio
        - profile.minimum_component_ratio,
    )
    separation = max(
        0.0,
        active.mask_ratio - inactive.mask_ratio,
    )
    value = 0.70 + mask_margin * 1.4 + component_margin * 1.6 + separation
    return round(min(0.99, value), 6)


def detect_dealer_marker(
    image: Image.Image,
    *,
    profile: DealerMarkerProfile | None = None,
    frame: str | int | None = None,
    session: str | None = None,
) -> DealerMarkerObservation:
    """Read player/opponent dealer-marker presence from one frame.

    A result is accepted only when exactly one reviewed marker zone is active.
    """
    profile = profile or DealerMarkerProfile()
    image = image.convert("RGB")
    player_signal = _marker_signal(image, profile.player_marker, profile)
    opponent_signal = _marker_signal(image, profile.opponent_marker, profile)

    actor: str | None
    issues: list[str] = []
    confidence = 0.0
    if player_signal.active and not opponent_signal.active:
        actor = "player"
        confidence = _confidence(player_signal, opponent_signal, profile)
    elif opponent_signal.active and not player_signal.active:
        actor = "opponent"
        confidence = _confidence(opponent_signal, player_signal, profile)
    elif player_signal.active and opponent_signal.active:
        actor = None
        issues.append("dealer_marker_ambiguous")
    else:
        actor = None
        issues.append("dealer_marker_unreadable")

    evidence_refs: tuple[str, ...] = ()
    if frame is not None:
        evidence_refs = (
            f"dealer_marker:{session or 'unknown'}:frame:{frame}",
        )

    return DealerMarkerObservation(
        actor=actor,
        confidence=confidence,
        player_signal=player_signal,
        opponent_signal=opponent_signal,
        issues=tuple(issues),
        frame=frame,
        session=session,
        evidence_refs=evidence_refs,
    )
