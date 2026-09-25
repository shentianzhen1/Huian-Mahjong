"""#69: read-only *system prompt* observations, never hand-shadow semantics.

This module consumes independently obtained, source-verified action-button
labels from the GAME's interactive prompt region. It does NOT inspect hand
brightness. Offered options are not executed actions; the absence of a
prompt is not a draw. Normal DRAW remains the responsibility of the
existing draw_visual temporal tracker.

A replay frame, playback controls or an unverified UI region fail closed.
There is deliberately no fixed source-resolution ROI or OCR truth claim.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Sequence

_SHA = re.compile(r"^[a-f0-9]{64}$")
_LABELS = {
    "吃": "CHI", "碰": "PENG", "杠": "KONG",
    "胡": "HU", "过": "PASS",
}
_ACTIONS = frozenset({"CHI", "PENG", "KONG", "HU"})


@dataclass(frozen=True)
class PublicActionPromptFrame:
    source_session: str
    source_sha256: str
    stream_epoch: int
    frame_index: int
    buttons_left_to_right: tuple[str, ...]
    source_frame_verified: bool
    action_button_region_verified: bool
    live_interactive_view_verified: bool
    replay_controls_visible: bool = False
    obscuring_overlay_visible: bool = False


@dataclass(frozen=True)
class PromptOfferReview:
    status: str
    offered_actions: tuple[str, ...]
    first_frame: int | None
    last_frame: int | None
    issues: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "schema_version": "public_action_prompt_offer_dev_v0_1",
            "development_only": True,
            "status": self.status,
            "offered_actions": list(self.offered_actions),
            "first_frame": self.first_frame,
            "last_frame": self.last_frame,
            "hand_shadow_used": False,
            "draw_requires_independent_draw_visual_transition": True,
            "requires_action_completion_evidence": True,
            "executed_action": "UNKNOWN",
            "claimed_tile": "UNKNOWN",
            "actor": "UNKNOWN",
            "formal_promotion_evidence": False,
            "safe_for_runtime": False,
            "safe_for_executor": False,
            "issues": list(self.issues),
        }


def _unknown(reason: str, *, no_offer: bool = False) -> PromptOfferReview:
    return PromptOfferReview(
        "NO_PROMPT_OBSERVED" if no_offer else "UNKNOWN",
        (), None, None, (reason,),
    )


def review_system_prompt(
    frames: Sequence[PublicActionPromptFrame],
    *,
    min_stable_frames: int = 2,
) -> PromptOfferReview:
    """Identify *offered* actions only from stable, verified live prompt ROIs.

    Caller supplies an independent UI button detector/OCR result; this pure
    review contract does not assert that the existing vision model already
    recognizes the buttons. The labels must be exact source UI labels.
    """
    if type(min_stable_frames) is not int or min_stable_frames < 2:
        raise ValueError("min_stable_frames must be >= 2")
    if not frames:
        return _unknown("no_source_frames")
    first = frames[0]
    if (
        not first.source_session
        or not isinstance(first.source_sha256, str)
        or not _SHA.fullmatch(first.source_sha256)
        or type(first.stream_epoch) is not int
        or first.stream_epoch < 0
    ):
        return _unknown("missing_or_invalid_source_scope")
    expected = (first.source_session, first.source_sha256, first.stream_epoch)
    previous_index = first.frame_index - 1 if type(first.frame_index) is int else -1
    stable: tuple[str, ...] | None = None
    for frame in frames:
        if (
            (frame.source_session, frame.source_sha256, frame.stream_epoch) != expected
            or type(frame.frame_index) is not int
            or frame.frame_index != previous_index + 1
        ):
            return _unknown("source_epoch_or_frame_discontinuity")
        previous_index = frame.frame_index
        if (
            frame.source_frame_verified is not True
            or frame.action_button_region_verified is not True
            or frame.live_interactive_view_verified is not True
            or frame.replay_controls_visible is not False
            or frame.obscuring_overlay_visible is not False
        ):
            return _unknown("replay_overlay_or_unverified_live_prompt")
        if (
            not isinstance(frame.buttons_left_to_right, tuple)
            or any(not isinstance(x, str) or x not in _LABELS
                   for x in frame.buttons_left_to_right)
            or len(set(frame.buttons_left_to_right)) != len(frame.buttons_left_to_right)
        ):
            # In particular, \"摸\" is NOT a claim button; DRAW is an
            # observed draw_visual transition, not a prompt inference.
            return _unknown("invalid_or_ambiguous_system_button_label")
        actions = tuple(sorted(_LABELS[x] for x in frame.buttons_left_to_right))
        if stable is None:
            stable = actions
        elif actions != stable:
            return _unknown("prompt_buttons_changed_during_stability_window")
    if len(frames) < min_stable_frames:
        return _unknown("insufficient_stable_prompt_frames")
    if not stable:
        return _unknown("no_prompt_does_not_prove_draw_or_pass", no_offer=True)
    if not _ACTIONS.intersection(stable):
        return _unknown("pass_only_not_an_action_claim")
    return PromptOfferReview(
        "STABLE_OFFERED_ACTIONS_NOT_EXECUTED", stable,
        first.frame_index, frames[-1].frame_index,
        ("system_prompt_is_option_not_confirmed_action",),
    )
