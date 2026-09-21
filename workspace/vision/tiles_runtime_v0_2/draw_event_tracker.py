"""Conservative temporal tracking for a visually separated drawn tile.

This module emits observations/events only.  It deliberately does not mutate
Rules, GameState, AI, Simulator, Hint Alpha, or Executor state.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


BBox = tuple[int, int, int, int]


class DrawState(str, Enum):
    STABLE_HAND = "STABLE_HAND"
    DRAW_STARTED = "DRAW_STARTED"
    DRAW_VISIBLE = "DRAW_VISIBLE"
    DRAW_MERGING = "DRAW_MERGING"
    DRAW_SETTLED = "DRAW_SETTLED"


@dataclass(frozen=True)
class VisualGeometryObservation:
    player: str
    frame: int
    hand_region_count: int
    draw_visual_bboxes: tuple[BBox, ...] = ()
    frame_state: str = "trusted"
    confidence: float = 1.0

    @property
    def draw_visual_count(self) -> int:
        return len(self.draw_visual_bboxes)

    @property
    def concealed_tile_count(self) -> int:
        return self.hand_region_count + self.draw_visual_count


@dataclass(frozen=True)
class DrawEvent:
    player: str
    tile_bbox: BBox
    tile_id: Optional[str]
    first_seen_frame: int
    settled_frame: int
    confidence: float


@dataclass(frozen=True)
class DrawTrackerOutput:
    state: DrawState
    concealed_tile_count: Optional[int]
    event: Optional[DrawEvent] = None
    trusted: bool = True
    reason: Optional[str] = None


class DrawEventTracker:
    """Track one draw across draw_visual -> animation -> settled hand.

    A single pending transaction owns the semantic tile count.  Consequently,
    the later hand-region increase settles that transaction instead of adding a
    second tile.
    """

    def __init__(self, settle_frames: int = 3):
        if settle_frames < 1:
            raise ValueError("settle_frames must be positive")
        self.settle_frames = settle_frames
        self.state = DrawState.STABLE_HAND
        self._stable_hand_count: Optional[int] = None
        self._pending_concealed_count: Optional[int] = None
        self._first_seen_frame: Optional[int] = None
        self._tile_bbox: Optional[BBox] = None
        self._confidence = 0.0
        self._settle_streak = 0

    def observe(self, observation: VisualGeometryObservation) -> DrawTrackerOutput:
        if observation.frame_state in {"occluded", "animation"}:
            if self._pending_concealed_count is not None:
                self.state = DrawState.DRAW_MERGING
            return self._output(False, "geometry_untrusted")
        if observation.frame_state != "trusted":
            return self._output(False, "unknown_frame_state")
        if observation.draw_visual_count > 1:
            return self._output(False, "ambiguous_multiple_draw_visual_components")

        if self._pending_concealed_count is None:
            if observation.draw_visual_count == 0:
                self._stable_hand_count = observation.hand_region_count
                self.state = DrawState.STABLE_HAND
                return self._output(True)
            self._pending_concealed_count = observation.concealed_tile_count
            self._first_seen_frame = observation.frame
            self._tile_bbox = observation.draw_visual_bboxes[0]
            self._confidence = observation.confidence
            self._settle_streak = 0
            self.state = DrawState.DRAW_STARTED
            return self._output(True)

        if observation.draw_visual_count == 1:
            if observation.concealed_tile_count != self._pending_concealed_count:
                return self._output(False, "pending_concealed_count_mismatch")
            self._tile_bbox = observation.draw_visual_bboxes[0]
            self._confidence = min(self._confidence, observation.confidence)
            self._settle_streak = 0
            self.state = DrawState.DRAW_VISIBLE
            return self._output(True)

        if observation.hand_region_count != self._pending_concealed_count:
            self.state = DrawState.DRAW_MERGING
            self._settle_streak = 0
            return self._output(False, "draw_not_yet_visually_settled")

        self._settle_streak += 1
        self.state = DrawState.DRAW_MERGING
        if self._settle_streak < self.settle_frames:
            return self._output(True)

        event = DrawEvent(
            player=observation.player,
            tile_bbox=self._tile_bbox or (0, 0, 0, 0),
            tile_id=None,
            first_seen_frame=self._first_seen_frame if self._first_seen_frame is not None else observation.frame,
            settled_frame=observation.frame,
            confidence=self._confidence,
        )
        self.state = DrawState.DRAW_SETTLED
        self._stable_hand_count = self._pending_concealed_count
        self._pending_concealed_count = None
        self._first_seen_frame = None
        self._tile_bbox = None
        self._settle_streak = 0
        return DrawTrackerOutput(self.state, self._stable_hand_count, event, True)

    def _output(self, trusted: bool, reason: Optional[str] = None) -> DrawTrackerOutput:
        count = self._pending_concealed_count
        if count is None:
            count = self._stable_hand_count
        return DrawTrackerOutput(self.state, count, None, trusted, reason)
