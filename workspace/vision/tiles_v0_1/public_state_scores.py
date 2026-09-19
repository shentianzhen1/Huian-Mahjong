"""OCR-assisted score reading for Huian PublicState.

The score glyphs are tiny, so raw single-pass OCR is intentionally not trusted.
V0.1 crops only the two score ROIs, tries a few nearby thresholds, accepts only
score pairs that conserve MATCH_TOTAL_SCORE, and may infer one missing side only
when the other side has exactly one plausible candidate.

The OCR backend is replaceable. TesseractCLIBackend is only the current
experimental baseline and is not an Executor gate.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
import shutil
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageOps

from huian.rules.dealer_base import MATCH_TOTAL_SCORE

from .public_state import (
    HuianPublicStateProfile,
    PublicStateCandidate,
    PublicStateObservation,
    fuse_public_state,
)


DEFAULT_THRESHOLDS = (70, 80, 90)


class OCRUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class OCRAttempt:
    threshold: int
    raw_text: str
    value: int | None


@dataclass(frozen=True)
class ScorePairRead:
    top_right_score: int | None
    bottom_left_score: int | None
    mode: str
    top_attempts: tuple[OCRAttempt, ...]
    bottom_attempts: tuple[OCRAttempt, ...]
    confidence: float
    source_frame: str | None = None
    safe_for_executor: bool = False

    @property
    def score_pair(self):
        if self.top_right_score is None or self.bottom_left_score is None:
            return None
        return self.top_right_score, self.bottom_left_score

    def to_candidate(self):
        return PublicStateCandidate(
            top_right_score=self.top_right_score,
            bottom_left_score=self.bottom_left_score,
            confidence=self.confidence,
            source_frame=self.source_frame,
        )


@dataclass(frozen=True)
class ScoreWindowRead:
    reads: tuple[ScorePairRead, ...]
    observation: PublicStateObservation
    safe_for_executor: bool = False


def _parse_digits(text):
    digits = "".join(re.findall(r"\d", text or ""))
    if not digits:
        return None
    return int(digits)


def prepare_score_gray(image, *, scale=8):
    """Return the grayscale/autocontrast score image used by the fast OCR pass."""
    if isinstance(scale, bool) or int(scale) <= 0:
        raise ValueError("scale must be a positive integer")
    gray = ImageOps.grayscale(image)
    gray = gray.resize(
        (gray.width * int(scale), gray.height * int(scale)),
        Image.Resampling.LANCZOS,
    )
    return np.asarray(ImageOps.autocontrast(gray))


def prepare_score_crop(image, *, threshold=80, scale=12, border=30):
    """Return a binary ndarray tuned for the tiny target-room score font."""
    if isinstance(threshold, bool) or not 0 <= int(threshold) <= 255:
        raise ValueError("threshold must be an integer between 0 and 255")
    if isinstance(scale, bool) or int(scale) <= 0:
        raise ValueError("scale must be a positive integer")
    if isinstance(border, bool) or int(border) < 0:
        raise ValueError("border must be a non-negative integer")

    rgb = np.asarray(image.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    enlarged = cv2.resize(
        gray,
        None,
        fx=int(scale),
        fy=int(scale),
        interpolation=cv2.INTER_CUBIC,
    )
    _, binary = cv2.threshold(
        enlarged, int(threshold), 255, cv2.THRESH_BINARY
    )
    if border:
        binary = cv2.copyMakeBorder(
            binary,
            int(border),
            int(border),
            int(border),
            int(border),
            cv2.BORDER_CONSTANT,
            value=0,
        )
    return binary


class TesseractCLIBackend:
    """Digits-only wrapper around an installed tesseract executable."""

    def __init__(self, command="tesseract", timeout_seconds=3.0):
        self.command = command
        self.timeout_seconds = float(timeout_seconds)

    def available(self):
        return shutil.which(self.command) is not None

    def __call__(self, binary_image):
        if not self.available():
            raise OCRUnavailable(
                f"{self.command!r} is not installed or not on PATH"
            )
        ok, encoded = cv2.imencode(".png", binary_image)
        if not ok:
            raise RuntimeError("failed to encode score crop for OCR")

        command = [
            self.command,
            "stdin",
            "stdout",
            "--psm",
            "7",
            "--oem",
            "3",
            "-c",
            "tessedit_char_whitelist=0123456789",
            "-c",
            "user_defined_dpi=300",
        ]
        try:
            result = subprocess.run(
                command,
                input=encoded.tobytes(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            raise OCRUnavailable(
                f"{self.command!r} is not installed or not on PATH"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise OCRUnavailable("score OCR timed out") from exc

        if result.returncode != 0:
            raise OCRUnavailable(
                "score OCR failed: "
                + result.stderr.decode("utf-8", errors="replace").strip()
            )
        return result.stdout.decode("utf-8", errors="replace").strip()


def _attempts(image, backend, thresholds):
    rows = []
    for threshold in thresholds:
        raw = backend(prepare_score_crop(image, threshold=threshold))
        value = _parse_digits(raw)
        if value is not None and not 0 <= value <= MATCH_TOTAL_SCORE:
            value = None
        rows.append(OCRAttempt(int(threshold), raw, value))
    return tuple(rows)


def _rank_candidates(attempts):
    values = [attempt.value for attempt in attempts if attempt.value is not None]
    counts = Counter(values)
    return tuple(value for value, _ in counts.most_common())


def decode_score_candidates(
    top_candidates,
    bottom_candidates,
    *,
    total_score=MATCH_TOTAL_SCORE,
):
    """Decode a score pair without silently repairing ambiguous reads."""
    top_candidates = tuple(top_candidates)
    bottom_candidates = tuple(bottom_candidates)

    for top in top_candidates:
        for bottom in bottom_candidates:
            if top + bottom == total_score:
                return top, bottom, "direct"

    if len(top_candidates) == 1 and not bottom_candidates:
        top = top_candidates[0]
        bottom = total_score - top
        if 0 <= bottom <= total_score:
            return top, bottom, "inferred_bottom"

    if len(bottom_candidates) == 1 and not top_candidates:
        bottom = bottom_candidates[0]
        top = total_score - bottom
        if 0 <= top <= total_score:
            return top, bottom, "inferred_top"

    return None, None, "invalid"


def read_score_pair(
    image,
    *,
    profile=None,
    backend=None,
    thresholds=DEFAULT_THRESHOLDS,
    source_frame=None,
    gray_first=True,
):
    """Read both visible scores from one PIL frame."""
    profile = profile or HuianPublicStateProfile()
    backend = backend or TesseractCLIBackend()
    crops = profile.crops(image)

    if gray_first:
        raw_top_gray = backend(prepare_score_gray(crops["top_right_score"]))
        raw_bottom_gray = backend(prepare_score_gray(crops["bottom_left_score"]))
        top_gray = _parse_digits(raw_top_gray)
        bottom_gray = _parse_digits(raw_bottom_gray)
        if top_gray is not None and not 0 <= top_gray <= MATCH_TOTAL_SCORE:
            top_gray = None
        if bottom_gray is not None and not 0 <= bottom_gray <= MATCH_TOTAL_SCORE:
            bottom_gray = None

        if (
            top_gray is not None
            and bottom_gray is not None
            and top_gray + bottom_gray == MATCH_TOTAL_SCORE
        ):
            return ScorePairRead(
                top_right_score=top_gray,
                bottom_left_score=bottom_gray,
                mode="gray_direct",
                top_attempts=(OCRAttempt(-1, raw_top_gray, top_gray),),
                bottom_attempts=(OCRAttempt(-1, raw_bottom_gray, bottom_gray),),
                confidence=1.0,
                source_frame=source_frame,
                safe_for_executor=False,
            )
        if top_gray is not None and bottom_gray is None:
            inferred = MATCH_TOTAL_SCORE - top_gray
            return ScorePairRead(
                top_right_score=top_gray,
                bottom_left_score=inferred,
                mode="gray_inferred_bottom",
                top_attempts=(OCRAttempt(-1, raw_top_gray, top_gray),),
                bottom_attempts=(OCRAttempt(-1, raw_bottom_gray, None),),
                confidence=0.75,
                source_frame=source_frame,
                safe_for_executor=False,
            )
        if bottom_gray is not None and top_gray is None:
            inferred = MATCH_TOTAL_SCORE - bottom_gray
            return ScorePairRead(
                top_right_score=inferred,
                bottom_left_score=bottom_gray,
                mode="gray_inferred_top",
                top_attempts=(OCRAttempt(-1, raw_top_gray, None),),
                bottom_attempts=(OCRAttempt(-1, raw_bottom_gray, bottom_gray),),
                confidence=0.75,
                source_frame=source_frame,
                safe_for_executor=False,
            )

    top_attempts = _attempts(
        crops["top_right_score"], backend, thresholds
    )
    bottom_attempts = _attempts(
        crops["bottom_left_score"], backend, thresholds
    )
    top_candidates = _rank_candidates(top_attempts)
    bottom_candidates = _rank_candidates(bottom_attempts)
    top, bottom, mode = decode_score_candidates(
        top_candidates, bottom_candidates
    )

    confidence = {
        "direct": 1.0,
        "inferred_bottom": 0.75,
        "inferred_top": 0.75,
        "invalid": 0.0,
    }[mode]
    return ScorePairRead(
        top_right_score=top,
        bottom_left_score=bottom,
        mode=mode,
        top_attempts=top_attempts,
        bottom_attempts=bottom_attempts,
        confidence=confidence,
        source_frame=source_frame,
        safe_for_executor=False,
    )


def read_score_window(
    images,
    *,
    profile=None,
    backend=None,
    thresholds=DEFAULT_THRESHOLDS,
    previous=None,
    expected_scores=None,
    minimum_votes=2,
):
    """Read nearby frames and fuse them through PublicState guards."""
    backend = backend or TesseractCLIBackend()
    reads = tuple(
        read_score_pair(
            image,
            profile=profile,
            backend=backend,
            thresholds=thresholds,
            source_frame=str(index),
            gray_first=True,
        )
        for index, image in enumerate(images)
    )
    observation = fuse_public_state(
        [read.to_candidate() for read in reads],
        previous=previous,
        expected_scores=expected_scores,
        minimum_votes=minimum_votes,
    )
    return ScoreWindowRead(
        reads=reads,
        observation=observation,
        safe_for_executor=False,
    )
