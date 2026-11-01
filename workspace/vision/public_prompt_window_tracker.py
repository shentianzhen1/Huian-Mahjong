"""#69: turn frame-level system prompt offers into a source-scoped UI timeline.

The target's nine existing videos are REPLAYS, not live button ground truth.
This observer only accepts a separately verified LIVE_INTERACTIVE capture and
source-verified, contiguous game-button observations. It does not read/need
concealed-hand shadows and does NOT infer a claim, PASS or DRAW from disappearance.

This is a read-only development-side input to future match reconstruction,
NOT an executor/Hint/Rules/AI interface and not a trained pixel classifier.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from workspace.vision.public_action_prompt import (
    PublicActionPromptFrame, review_system_prompt,
)

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_VALID_LABELS = frozenset({"吃", "碰", "杠", "胡", "过"})


@dataclass(frozen=True)
class PromptWindowTransition:
    status: str
    window_id: int
    first_frame: int | None
    last_frame: int | None
    offered_actions: tuple[str, ...]
    previous_actions: tuple[str, ...]
    issues: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        # No original file name, private SHA, player ID or raw crop bytes.
        return {
            "schema_version": "public_prompt_window_dev_v0_1",
            "development_only": True,
            "status": self.status,
            "window_id": self.window_id,
            "first_frame": self.first_frame,
            "last_frame": self.last_frame,
            "offered_actions": list(self.offered_actions),
            "previous_actions": list(self.previous_actions),
            "action_selection": "UNKNOWN",
            "pass_selected": "UNKNOWN",
            "draw_event": "UNKNOWN",
            "requires_independent_claim_or_draw_evidence": True,
            "hand_shadow_used": False,
            "formal_promotion_evidence": False,
            "safe_for_runtime": False,
            "safe_for_executor": False,
            "issues": list(self.issues),
        }


class SystemPromptWindowTracker:
    """Incremental prompt visibility with explicit UNKNOWN at every interruption.

    Emits OPENED once for stable real action choices, OPTIONS_CHANGED for
    changed stable choices, DISAPPEARED_UNATTRIBUTED only after stable empty
    live-button ROI, and INTERRUPTED_UNKNOWN upon source/replay/gap/invalid
    data. Neither a vanished prompt nor any single source frame is proof
    that the user selected an action, passed, or drew a tile.

    Window IDs are local to this tracker, not stable cross-source identifiers.
    """

    def __init__(self, min_stable_frames: int = 2):
        if type(min_stable_frames) is not int or min_stable_frames < 2:
            raise ValueError("min_stable_frames must be an integer >= 2")
        self.min_stable_frames = min_stable_frames
        self._scope: tuple[str, str, int] | None = None
        self._last_index: int | None = None
        self._pending: list[PublicActionPromptFrame] = []
        self._pending_signature: tuple[str, ...] | None = None
        self._active_signature: tuple[str, ...] | None = None
        self._active_actions: tuple[str, ...] = ()
        self._window_id = 0

    def _reset(self) -> None:
        self._pending = []
        self._pending_signature = None
        self._active_signature = None
        self._active_actions = ()

    def _interrupt(self, reason: str) -> tuple[PromptWindowTransition, ...]:
        old_actions = self._active_actions
        active = self._active_signature is not None
        self._reset()
        if not active:
            return ()
        return (PromptWindowTransition(
            "PROMPT_INTERRUPTED_UNKNOWN",
            self._window_id, None, self._last_index,
            (), old_actions, (reason,),
        ),)

    def reset_for_hand_boundary(self) -> tuple[PromptWindowTransition, ...]:
        """Discard a pending offer on a confirmed hand boundary, not as PASS."""
        out = self._interrupt("hand_boundary_without_confirmed_selection")
        self._scope = None
        self._last_index = None
        return out

    def observe(
        self, frame: PublicActionPromptFrame,
    ) -> tuple[PromptWindowTransition, ...]:
        if (
            not isinstance(frame.source_session, str)
            or not frame.source_session
            or not isinstance(frame.source_sha256, str)
            or not _SHA256.fullmatch(frame.source_sha256)
            or type(frame.stream_epoch) is not int
            or frame.stream_epoch < 0
            or type(frame.frame_index) is not int
            or frame.frame_index < 0
        ):
            return self._interrupt("untrusted_source_session_sha_epoch_or_frame")
        scope = (
            frame.source_session, frame.source_sha256, frame.stream_epoch,
        )
        emitted: list[PromptWindowTransition] = []
        if self._scope is None:
            self._scope = scope
        elif scope != self._scope:
            emitted.extend(self._interrupt("source_or_epoch_changed"))
            self._scope = scope
            self._last_index = None
        elif (
            self._last_index is not None
            and frame.frame_index != self._last_index + 1
        ):
            emitted.extend(self._interrupt("frame_gap_or_repeated_source_frame"))
            self._last_index = None

        self._last_index = frame.frame_index
        if (
            frame.source_frame_verified is not True
            or frame.action_button_region_verified is not True
            or frame.live_interactive_view_verified is not True
            or frame.independently_verified_capture_mode != "LIVE_INTERACTIVE"
            or frame.capture_mode_verified_without_buttons is not True
            or frame.replay_controls_visible is not False
            or frame.obscuring_overlay_visible is not False
        ):
            emitted.extend(self._interrupt("unverified_live_ui_or_replay_overlay"))
            return tuple(emitted)

        buttons = frame.buttons_left_to_right
        if (
            not isinstance(buttons, tuple)
            or any(not isinstance(v, str) or v not in _VALID_LABELS
                   for v in buttons)
            or len(buttons) != len(set(buttons))
        ):
            emitted.extend(self._interrupt("unsupported_or_duplicate_button"))
            return tuple(emitted)

        signature = tuple(sorted(buttons))
        if signature == self._active_signature:
            self._pending = []
            self._pending_signature = None
            return tuple(emitted)
        if signature != self._pending_signature:
            self._pending = [frame]
            self._pending_signature = signature
        else:
            self._pending.append(frame)
        if len(self._pending) < self.min_stable_frames:
            return tuple(emitted)
        reviewed = review_system_prompt(
            self._pending, min_stable_frames=self.min_stable_frames,
        )
        first = self._pending[0].frame_index
        last = self._pending[-1].frame_index
        self._pending = []
        self._pending_signature = None

        if reviewed.status == "NO_PROMPT_OBSERVED":
            if self._active_signature is not None:
                emitted.append(PromptWindowTransition(
                    "PROMPT_DISAPPEARED_UNATTRIBUTED",
                    self._window_id, first, last, (), self._active_actions,
                    ("empty_live_prompt_is_not_pass_draw_or_claim",),
                ))
            self._active_signature = None
            self._active_actions = ()
        elif reviewed.status == "STABLE_OFFERED_ACTIONS_NOT_EXECUTED":
            old = self._active_actions
            opened = self._active_signature is None
            if opened:
                self._window_id += 1
            self._active_signature = signature
            self._active_actions = reviewed.offered_actions
            emitted.append(PromptWindowTransition(
                "PROMPT_OPENED" if opened else "PROMPT_OPTIONS_CHANGED",
                self._window_id, first, last,
                reviewed.offered_actions, old,
                ("system_offers_are_not_confirmed_actions",),
            ))
        else:
            emitted.extend(self._interrupt(
                "stable_prompt_state_unrecognized_or_pass_only"
            ))
        return tuple(emitted)
