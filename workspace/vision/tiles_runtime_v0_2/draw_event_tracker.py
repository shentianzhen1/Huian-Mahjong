"""Conservative draw/discard/resort temporal tracking for Vision V0.2.

The tracker owns semantic concealed-tile *counts*, not stable slot identities.
It emits observations and events only; it does not mutate Rules, GameState, AI,
Simulator, Hint Alpha, or Executor state.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


BBox = tuple[int, int, int, int]


class DrawState(str, Enum):
    STABLE_HAND = "STABLE_HAND"
    DRAW_VISIBLE = "DRAW_VISIBLE"
    DISCARD_CONFIRMED = "DISCARD_CONFIRMED"
    HAND_RESORTING = "HAND_RESORTING"
    DISCARD_DRAWN_TILE = "DISCARD_DRAWN_TILE"


class DiscardSource(str, Enum):
    HAND = "hand"
    DRAW_VISUAL = "draw_visual"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class VisualGeometryObservation:
    player: str
    frame: int
    hand_region_count: int
    draw_visual_bboxes: tuple[BBox, ...] = ()
    frame_state: str = "trusted"
    animation_type: Optional[str] = None
    confidence: float = 1.0

    @property
    def draw_visual_count(self) -> int:
        return len(self.draw_visual_bboxes)

    @property
    def visible_concealed_count(self) -> int:
        return self.hand_region_count + self.draw_visual_count


@dataclass(frozen=True)
class DrawEvent:
    player: str
    tile_bbox: BBox
    tile_id: Optional[str]
    first_seen_frame: int
    confidence: float


@dataclass(frozen=True)
class DiscardConfirmation:
    player: str
    frame: int
    source_region: DiscardSource
    tile_id: Optional[str] = None
    confidence: float = 1.0


@dataclass(frozen=True)
class DiscardEvent:
    player: str
    frame: int
    source_region: DiscardSource
    tile_id: Optional[str]
    confidence: float


@dataclass(frozen=True)
class DrawTrackerOutput:
    state: DrawState
    concealed_tile_count: Optional[int]
    draw_event: Optional[DrawEvent] = None
    discard_event: Optional[DiscardEvent] = None
    trusted: bool = True
    stable_for_hint: bool = False
    reason: Optional[str] = None


class DrawEventTracker:
    """Track draw, confirmed discard, and automatic post-discard resort.

    The semantic count increments exactly once when ``draw_visual`` first
    appears. A confirmed discard decrements it exactly once. Later movement of
    that tile into the sorted hand changes only visual geometry.
    """

    def __init__(self, settle_frames: int = 3):
        if settle_frames < 1:
            raise ValueError("settle_frames must be positive")
        self.settle_frames = settle_frames
        self.state = DrawState.STABLE_HAND
        self._player: Optional[str] = None
        self._concealed_count: Optional[int] = None
        self._draw_bbox: Optional[BBox] = None
        self._settle_streak = 0

    def observe(self, observation: VisualGeometryObservation) -> DrawTrackerOutput:
        if not self._accept_player(observation.player):
            return self._output(False, "player_changed_during_pending_event")
        if observation.draw_visual_count > 1:
            return self._output(False, "ambiguous_multiple_draw_visual_components")
        if observation.frame_state == "animation":
            if observation.animation_type == "hand_resort":
                if self.state in {DrawState.DISCARD_CONFIRMED, DrawState.HAND_RESORTING}:
                    self.state = DrawState.HAND_RESORTING
                    self._settle_streak = 0
                    return self._output(False, "hand_resort_animation")
                return self._output(False, "hand_resort_without_discard_confirmation")
            return self._output(False, "geometry_animation_untrusted")
        if observation.frame_state == "occluded":
            return self._output(False, "geometry_occluded")
        if observation.frame_state != "trusted":
            return self._output(False, "unknown_frame_state")

        if self.state == DrawState.STABLE_HAND:
            if observation.draw_visual_count == 1:
                baseline = self._concealed_count
                if baseline is None:
                    baseline = observation.hand_region_count
                if observation.hand_region_count != baseline:
                    return self._output(False, "draw_visible_hand_count_changed")
                self._concealed_count = baseline + 1
                self._draw_bbox = observation.draw_visual_bboxes[0]
                self.state = DrawState.DRAW_VISIBLE
                event = DrawEvent(
                    player=observation.player,
                    tile_bbox=self._draw_bbox,
                    tile_id=None,
                    first_seen_frame=observation.frame,
                    confidence=observation.confidence,
                )
                return self._output(True, draw_event=event)
            if self._concealed_count is None:
                self._concealed_count = observation.hand_region_count
            elif observation.hand_region_count != self._concealed_count:
                return self._output(False, "unconfirmed_concealed_count_change")
            return self._output(True)

        if self.state == DrawState.DRAW_VISIBLE:
            if observation.draw_visual_count == 0:
                return self._output(False, "draw_visual_disappeared_without_discard_confirmation")
            if observation.visible_concealed_count != self._concealed_count:
                return self._output(False, "draw_visible_count_mismatch")
            self._draw_bbox = observation.draw_visual_bboxes[0]
            return self._output(True)

        if self.state in {DrawState.DISCARD_CONFIRMED, DrawState.HAND_RESORTING}:
            if observation.draw_visual_count == 1:
                # A confirmed hand discard may be visible for a short period
                # before automatic sorting starts. It is not another draw.
                if observation.visible_concealed_count != self._concealed_count:
                    return self._output(False, "post_discard_visible_count_mismatch")
                return self._output(True)
            return self._settle_stable_hand(observation, resort=True)

        if self.state == DrawState.DISCARD_DRAWN_TILE:
            if observation.draw_visual_count:
                return self._output(False, "discarded_draw_visual_still_present")
            return self._settle_stable_hand(observation, resort=False)

        return self._output(False, "unknown_tracker_state")

    def confirm_discard(self, confirmation: DiscardConfirmation) -> DrawTrackerOutput:
        """Apply one externally confirmed discard without using slot identity."""
        if not self._accept_player(confirmation.player):
            return self._output(False, "discard_player_mismatch")
        if self.state != DrawState.DRAW_VISIBLE or self._concealed_count is None:
            return self._output(False, "discard_without_visible_draw")
        if confirmation.source_region == DiscardSource.UNKNOWN:
            return self._output(False, "discard_source_unknown")

        self._concealed_count -= 1
        event = DiscardEvent(
            player=confirmation.player,
            frame=confirmation.frame,
            source_region=confirmation.source_region,
            tile_id=confirmation.tile_id,
            confidence=confirmation.confidence,
        )
        self._settle_streak = 0
        if confirmation.source_region == DiscardSource.DRAW_VISUAL:
            self._draw_bbox = None
            self.state = DrawState.DISCARD_DRAWN_TILE
        else:
            self.state = DrawState.DISCARD_CONFIRMED
        return self._output(True, discard_event=event)

    def _settle_stable_hand(
        self, observation: VisualGeometryObservation, *, resort: bool
    ) -> DrawTrackerOutput:
        if observation.hand_region_count != self._concealed_count:
            self._settle_streak = 0
            if resort:
                self.state = DrawState.HAND_RESORTING
            return self._output(False, "post_discard_hand_count_not_stable")
        self._settle_streak += 1
        if resort:
            self.state = DrawState.HAND_RESORTING
        if self._settle_streak < self.settle_frames:
            return self._output(True)
        self.state = DrawState.STABLE_HAND
        self._draw_bbox = None
        self._settle_streak = 0
        return self._output(True)

    def _accept_player(self, player: str) -> bool:
        if self._player is None:
            self._player = player
        return self._player == player

    def _output(
        self,
        trusted: bool,
        reason: Optional[str] = None,
        *,
        draw_event: Optional[DrawEvent] = None,
        discard_event: Optional[DiscardEvent] = None,
    ) -> DrawTrackerOutput:
        stable_for_hint = trusted and self.state in {
            DrawState.STABLE_HAND,
            DrawState.DRAW_VISIBLE,
        }
        return DrawTrackerOutput(
            state=self.state,
            concealed_tile_count=self._concealed_count,
            draw_event=draw_event,
            discard_event=discard_event,
            trusted=trusted,
            stable_for_hint=stable_for_hint,
            reason=reason,
        )
