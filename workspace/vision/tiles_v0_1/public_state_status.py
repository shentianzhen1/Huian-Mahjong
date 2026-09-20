"""Read remaining-wall count and current hand index from the target-room UI."""
from __future__ import annotations

from dataclasses import dataclass
import re

import numpy as np
from PIL import Image, ImageOps

from .public_state import (
    HuianPublicStateProfile,
    PublicStateCandidate,
    PublicStateObservation,
)
from .public_state_scores import TesseractCLIBackend


_STATUS_CHARS = re.compile(r"[0-9/]")
_REMAINING_FALLBACK_RIGHT_KEEP = 0.86


def prepare_status_crop(image, *, scale=10):
    if isinstance(scale, bool) or int(scale) <= 0:
        raise ValueError("scale must be a positive integer")
    gray = ImageOps.grayscale(image)
    gray = gray.resize(
        (gray.width * int(scale), gray.height * int(scale)),
        Image.Resampling.LANCZOS,
    )
    return np.asarray(ImageOps.autocontrast(gray))


def _clean_status_text(text):
    return "".join(_STATUS_CHARS.findall(text or ""))


def _trim_remaining_right_edge(image):
    """Trim the UI glyph immediately right of the wall count.

    Current target-room frames sometimes include the leading edge of the
    following Chinese character in the normalized remaining-tiles ROI. Tesseract
    may append that edge as an extra digit (for example 98 -> 985). This crop is
    deliberately a fallback only: a valid primary parse is never replaced.
    """
    keep = max(1, int(round(image.width * _REMAINING_FALLBACK_RIGHT_KEEP)))
    return image.crop((0, 0, keep, image.height))


def parse_remaining_tiles(text):
    """Parse the yellow wall count; target font often OCRs 7 as '/'."""
    cleaned = _clean_status_text(text).replace("/", "7")
    if not cleaned or not cleaned.isdigit():
        return None
    value = int(cleaned)
    if 16 <= value <= 144:
        return value
    return None


def parse_hand_progress(text):
    """Parse N/8; tolerate the target font's 7 -> '/' confusion."""
    cleaned = _clean_status_text(text)
    if cleaned == "//8":
        return 7
    if len(cleaned) == 3 and cleaned[1:] == "/8":
        if cleaned[0].isdigit():
            value = int(cleaned[0])
            return value if 1 <= value <= 8 else None
    if len(cleaned) == 2 and cleaned[1] == "8" and cleaned[0].isdigit():
        value = int(cleaned[0])
        return value if 1 <= value <= 8 else None
    return None


def infer_missing_hand_from_transition(
    hand_number,
    *,
    previous=None,
    current_score_pair=None,
):
    """Infer only the next hand when a trusted score pair changed.

    This is deliberately narrow: it never guesses within the same score state,
    never skips more than one hand, and never infers beyond hand 8.
    """
    if hand_number is not None:
        return hand_number, False
    if previous is None or previous.hand_number is None:
        return None, False
    if previous.hand_number >= 8:
        return None, False
    if previous.score_pair is None or current_score_pair is None:
        return None, False
    if tuple(previous.score_pair) == tuple(current_score_pair):
        return None, False
    return previous.hand_number + 1, True


@dataclass(frozen=True)
class StatusLineRead:
    remaining_tiles: int | None
    hand_number: int | None
    raw_remaining: str
    raw_hand_progress: str
    hand_inferred_from_transition: bool = False
    issues: tuple[str, ...] = ()
    safe_for_executor: bool = False
    remaining_mode: str = "primary"
    raw_remaining_fallback: str | None = None

    def to_candidate(
        self,
        *,
        score_pair=None,
        previous: PublicStateObservation | None = None,
        source_frame=None,
    ):
        hand, inferred = infer_missing_hand_from_transition(
            self.hand_number,
            previous=previous,
            current_score_pair=score_pair,
        )
        issues = list(self.issues)
        if self.remaining_tiles is None:
            issues.append("remaining_unreadable")
        if hand is None:
            issues.append("hand_unreadable")
        top = bottom = None
        if score_pair is not None:
            top, bottom = score_pair
        confidence = 0.90
        if inferred:
            confidence = 0.80
        if hand is None and self.remaining_tiles is None:
            confidence = 0.0
        return PublicStateCandidate(
            top_right_score=top,
            bottom_left_score=bottom,
            hand_number=hand,
            remaining_tiles=self.remaining_tiles,
            confidence=confidence,
            source_frame=source_frame,
        )


class TesseractStatusReader:
    def __init__(self, backend=None):
        self.backend = backend or TesseractCLIBackend(
            whitelist="0123456789/"
        )

    def read(self, image, profile=None):
        profile = profile or HuianPublicStateProfile()
        crops = profile.crops(image)
        raw_remaining = self.backend(
            prepare_status_crop(crops["remaining_tiles"])
        )
        remaining = parse_remaining_tiles(raw_remaining)
        raw_remaining_fallback = None
        remaining_mode = "primary"
        if remaining is None:
            raw_remaining_fallback = self.backend(
                prepare_status_crop(
                    _trim_remaining_right_edge(crops["remaining_tiles"])
                )
            )
            fallback = parse_remaining_tiles(raw_remaining_fallback)
            if fallback is not None:
                remaining = fallback
                remaining_mode = "right_trim_fallback"
            else:
                remaining_mode = "invalid"

        raw_hand = self.backend(
            prepare_status_crop(crops["hand_progress"])
        )
        hand = parse_hand_progress(raw_hand)
        issues = []
        if remaining is None:
            issues.append("remaining_unreadable")
        if hand is None:
            issues.append("hand_unreadable")
        return StatusLineRead(
            remaining_tiles=remaining,
            hand_number=hand,
            raw_remaining=raw_remaining,
            raw_hand_progress=raw_hand,
            issues=tuple(issues),
            safe_for_executor=False,
            remaining_mode=remaining_mode,
            raw_remaining_fallback=raw_remaining_fallback,
        )
