"""Optional Tesseract-backed reader for target-room public score digits.

The Mahjong project deliberately keeps OCR separate from state trust:
- this module only reads pixels into candidate score values;
- public_state.py decides whether those values are physically consistent.

Tesseract is an external executable, not a Python dependency. Windows users may
pass an explicit executable path. Missing/failed OCR returns an issue instead of
guessing a score.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from numbers import Integral
from pathlib import Path
import re
import subprocess

from PIL import Image, ImageOps

from huian.rules.dealer_base import MATCH_TOTAL_SCORE

from .public_state import HuianPublicStateProfile, PublicStateCandidate


_DIGITS = re.compile(r"\d+")


@dataclass(frozen=True)
class ScoreOCRResult:
    top_right_score: int | None
    bottom_left_score: int | None
    raw_top_right: str
    raw_bottom_left: str
    derived_side: str | None = None
    issues: tuple[str, ...] = ()
    safe_for_executor: bool = False

    @property
    def score_pair(self):
        if self.top_right_score is None or self.bottom_left_score is None:
            return None
        return self.top_right_score, self.bottom_left_score

    @property
    def valid(self):
        return not self.issues and self.score_pair is not None

    def to_candidate(self, *, source_frame=None):
        # Heuristic confidence only. The real gate is physical + temporal
        # validation in fuse_public_state().
        confidence = 0.95 if self.derived_side is None else 0.85
        if not self.valid:
            confidence = 0.0
        return PublicStateCandidate(
            top_right_score=self.top_right_score,
            bottom_left_score=self.bottom_left_score,
            confidence=confidence,
            source_frame=source_frame,
        )


def preprocess_score_crop(image, *, scale=8):
    """Upscale tiny score digits while preserving the target UI font."""
    if isinstance(scale, bool) or not isinstance(scale, Integral) or scale < 1:
        raise ValueError("scale must be a positive integer")
    gray = ImageOps.grayscale(image)
    gray = gray.resize(
        (gray.width * int(scale), gray.height * int(scale)),
        Image.Resampling.LANCZOS,
    )
    return ImageOps.autocontrast(gray)


def parse_score_text(text):
    """Return one plausible 0..2000 score from OCR text, else None."""
    if text is None:
        return None
    digits = "".join(_DIGITS.findall(str(text)))
    if not digits:
        return None
    try:
        value = int(digits)
    except ValueError:
        return None
    if 0 <= value <= MATCH_TOTAL_SCORE:
        return value
    return None


def reconcile_score_pair(top_right, bottom_left):
    """Apply the target-room 2000-point conservation law conservatively."""
    top = top_right if isinstance(top_right, Integral) and not isinstance(top_right, bool) else None
    bottom = bottom_left if isinstance(bottom_left, Integral) and not isinstance(bottom_left, bool) else None

    if top is not None and not 0 <= top <= MATCH_TOTAL_SCORE:
        top = None
    if bottom is not None and not 0 <= bottom <= MATCH_TOTAL_SCORE:
        bottom = None

    if top is not None and bottom is not None:
        if top + bottom == MATCH_TOTAL_SCORE:
            return int(top), int(bottom), None, ()
        return None, None, None, ("score_sum_mismatch",)

    if top is not None:
        return int(top), MATCH_TOTAL_SCORE - int(top), "bottom_left", ()
    if bottom is not None:
        return MATCH_TOTAL_SCORE - int(bottom), int(bottom), "top_right", ()
    return None, None, None, ("score_unreadable",)


class TesseractScoreReader:
    """Read the two public score boxes with a digit-only Tesseract pass."""

    def __init__(self, executable="tesseract", *, timeout_seconds=5):
        self.executable = str(executable)
        self.timeout_seconds = float(timeout_seconds)
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    def _run_ocr(self, image):
        prepared = preprocess_score_crop(image)
        buffer = BytesIO()
        prepared.save(buffer, format="PNG")
        try:
            completed = subprocess.run(
                [
                    self.executable,
                    "stdin",
                    "stdout",
                    "--psm",
                    "7",
                    "-c",
                    "tessedit_char_whitelist=0123456789",
                ],
                input=buffer.getvalue(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout_seconds,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ""
        if completed.returncode != 0:
            return ""
        return completed.stdout.decode("utf-8", errors="ignore").strip()

    def read_scores(self, image, profile=None):
        profile = profile or HuianPublicStateProfile()
        crops = profile.crops(image)
        raw_top = self._run_ocr(crops["top_right_score"])
        raw_bottom = self._run_ocr(crops["bottom_left_score"])

        top = parse_score_text(raw_top)
        bottom = parse_score_text(raw_bottom)
        top, bottom, derived_side, issues = reconcile_score_pair(top, bottom)
        return ScoreOCRResult(
            top_right_score=top,
            bottom_left_score=bottom,
            raw_top_right=raw_top,
            raw_bottom_left=raw_bottom,
            derived_side=derived_side,
            issues=issues,
            safe_for_executor=False,
        )


def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Read Huian target-room public scores from one screenshot")
    parser.add_argument("image")
    parser.add_argument(
        "--tesseract",
        default="tesseract",
        help="Tesseract executable name/path (for Windows, pass tesseract.exe path)",
    )
    args = parser.parse_args()

    with Image.open(args.image) as source:
        result = TesseractScoreReader(args.tesseract).read_scores(
            source.convert("RGB")
        )
    print(json.dumps({
        "top_right_score": result.top_right_score,
        "bottom_left_score": result.bottom_left_score,
        "raw_top_right": result.raw_top_right,
        "raw_bottom_left": result.raw_bottom_left,
        "derived_side": result.derived_side,
        "issues": list(result.issues),
        "safe_for_executor": result.safe_for_executor,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
