"""Recorder V0.2: read-only capture with conservative per-hand recording."""

from .auto_recorder import (
    AutoHandRecorder, FrameRingBuffer, HandPhase,
    PhaseDetection, TemplatePhaseDetector,
)
from .media import FrameHealth, Recorder, snapshot

__all__ = [
    "AutoHandRecorder", "FrameHealth", "FrameRingBuffer", "HandPhase",
    "PhaseDetection", "Recorder", "TemplatePhaseDetector", "snapshot",
]
