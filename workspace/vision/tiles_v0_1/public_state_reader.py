"""Unified PublicState reader for the target Huian two-player room."""
from __future__ import annotations

from dataclasses import dataclass

from .public_state import (
    HuianPublicStateProfile,
    PublicStateCandidate,
    PublicStateObservation,
    fuse_public_state,
)
from .public_state_scores import (
    ScorePairRead,
    TesseractCLIBackend,
    read_score_pair,
)
from .public_state_status import (
    StatusLineRead,
    TesseractStatusReader,
    infer_missing_hand_from_transition,
)


@dataclass(frozen=True)
class PublicStateFrameRead:
    score: ScorePairRead
    status: StatusLineRead
    candidate: PublicStateCandidate
    issues: tuple[str, ...] = ()
    safe_for_executor: bool = False


@dataclass(frozen=True)
class PublicStateWindowRead:
    frames: tuple[PublicStateFrameRead, ...]
    observation: PublicStateObservation
    safe_for_executor: bool = False


def compose_public_candidate(
    score_read,
    status_read,
    *,
    previous=None,
    source_frame=None,
):
    """Combine independent score/status reads without weakening either guard."""
    score_pair = score_read.score_pair
    hand_number, hand_inferred = infer_missing_hand_from_transition(
        status_read.hand_number,
        previous=previous,
        current_score_pair=score_pair,
    )

    top = bottom = None
    if score_pair is not None:
        top, bottom = score_pair

    confidence_parts = []
    if score_pair is not None:
        confidence_parts.append(float(score_read.confidence))
    if status_read.remaining_tiles is not None:
        confidence_parts.append(0.90)
    if hand_number is not None:
        confidence_parts.append(0.80 if hand_inferred else 0.90)
    confidence = min(confidence_parts) if confidence_parts else 0.0

    issues = []
    if score_pair is None:
        issues.append("score_unreadable")
    if status_read.remaining_tiles is None:
        issues.append("remaining_unreadable")
    if hand_number is None:
        issues.append("hand_unreadable")
    if hand_inferred:
        issues.append("hand_inferred_from_score_transition")

    candidate = PublicStateCandidate(
        top_right_score=top,
        bottom_left_score=bottom,
        hand_number=hand_number,
        remaining_tiles=status_read.remaining_tiles,
        confidence=confidence,
        source_frame=source_frame,
    )
    return candidate, tuple(issues)


class PublicStateReader:
    """Read and conservatively fuse public match state from nearby frames."""

    def __init__(
        self,
        *,
        profile=None,
        score_backend=None,
        status_backend=None,
    ):
        self.profile = profile or HuianPublicStateProfile()
        self.score_backend = score_backend or TesseractCLIBackend(
            whitelist="0123456789"
        )
        self.status_reader = TesseractStatusReader(
            status_backend
            or TesseractCLIBackend(whitelist="0123456789/")
        )

    def read_frame(self, image, *, previous=None, source_frame=None):
        score = read_score_pair(
            image,
            profile=self.profile,
            backend=self.score_backend,
            source_frame=source_frame,
            gray_first=False,
        )
        status = self.status_reader.read(image, profile=self.profile)
        candidate, issues = compose_public_candidate(
            score,
            status,
            previous=previous,
            source_frame=source_frame,
        )
        return PublicStateFrameRead(
            score=score,
            status=status,
            candidate=candidate,
            issues=issues,
            safe_for_executor=False,
        )

    def read_window(
        self,
        images,
        *,
        previous=None,
        expected_scores=None,
        minimum_votes=2,
    ):
        frames = tuple(
            self.read_frame(
                image,
                previous=previous,
                source_frame=str(index),
            )
            for index, image in enumerate(images)
        )
        observation = fuse_public_state(
            [frame.candidate for frame in frames],
            previous=previous,
            expected_scores=expected_scores,
            minimum_votes=minimum_votes,
        )
        return PublicStateWindowRead(
            frames=frames,
            observation=observation,
            safe_for_executor=False,
        )
