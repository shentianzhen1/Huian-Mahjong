"""Source-scoped continuous-frame audit for Public Match Reconstruction #69.

This module only *evaluates* locked human-reviewed frame truth against
read-only tracker/assembler outputs. It never upgrades a visual candidate into
a DISCARD, decides Mahjong legality, trains a model, or promotes Runtime Vision.
Missing continuous truth or lineage raises instead of reporting fake metrics.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Sequence

from workspace.vision.public_candidate_tracker import (
    CandidateChannel,
    CandidateTrackerOutput,
    tracks_for_channel,
)
from workspace.vision.public_match_reconstruction import (
    EvidenceGrade,
    PublicActionKind,
    ReconstructedAction,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ACTORS = frozenset({"player", "opponent", "unknown"})
_EVENTS = frozenset({
    "DISCARD", "CHI", "PENG", "MING_GANG", "ADD_KONG", "HU",
})
_FOCUS = frozenset({"PRESENT", "ABSENT", "UNKNOWN"})
_TURN_METHODS = frozenset({"explicit_ui", "visible_hand_transition"})


def _frame(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("frame must be a nonnegative integer")
    return value


def _source(session: str, epoch: int) -> None:
    if not isinstance(session, str) or not session:
        raise ValueError("source_session is required")
    if type(epoch) is not int or epoch < 0:
        raise ValueError("stream_epoch must be a nonnegative integer")


@dataclass(frozen=True)
class ReviewedFrame:
    """Human truth for one sampled source frame, including negative frames.

    The event label refers to an action first *visibly occurring* on this
    frame. A public focus may be PRESENT during Hu, opening, or animation,
    and does NOT by itself mean DISCARD.
    """

    frame: int
    timestamp_seconds: float
    focus: str
    action: str
    actor: str
    turn_actor: str
    evidence_ref: str

    def __post_init__(self) -> None:
        _frame(self.frame)
        if not isinstance(self.timestamp_seconds, (int, float)) or isinstance(
            self.timestamp_seconds, bool
        ) or not 0 <= self.timestamp_seconds < float("inf"):
            raise ValueError("invalid timestamp_seconds")
        if self.focus not in _FOCUS:
            raise ValueError("focus must be PRESENT, ABSENT or UNKNOWN")
        if self.action not in _EVENTS | {"NONE", "UNKNOWN"}:
            raise ValueError("unsupported reviewed action")
        if self.actor not in _ACTORS or self.turn_actor not in _ACTORS:
            raise ValueError("unsupported reviewed actor")
        if self.action in _EVENTS and self.actor == "unknown":
            raise ValueError("unresolved actor must use UNKNOWN action truth")
        if self.action in {"NONE", "UNKNOWN"} and self.actor != "unknown":
            raise ValueError("NONE/UNKNOWN truth cannot assert an actor")
        if not self.evidence_ref:
            raise ValueError("each reviewed frame needs an independent raw-frame ref")


@dataclass(frozen=True)
class ReviewedSegment:
    """A locked, complete contiguous SAMPLE of raw-video frames.

    Consecutive sampled indices are separated by frame_step, even when the
    underlying video has a higher frame rate. No isolated cherry-picked JPG
    may be passed off as a reviewed continuous segment.
    """

    source_session: str
    source_sha256: str
    stream_epoch: int
    start_frame: int
    end_frame: int
    frame_step: int
    approved_by: str
    approval_ref: str
    perspective_ref: str
    frames: tuple[ReviewedFrame, ...]
    source_mode: str = "development"

    def __post_init__(self) -> None:
        _source(self.source_session, self.stream_epoch)
        if not _SHA256.fullmatch(self.source_sha256):
            raise ValueError("source_sha256 must be a lowercase SHA256")
        start, end = _frame(self.start_frame), _frame(self.end_frame)
        if type(self.frame_step) is not int or self.frame_step < 1:
            raise ValueError("frame_step must be positive")
        if start > end or (end - start) % self.frame_step:
            raise ValueError("segment frame bounds must align with frame_step")
        if not all((self.approved_by, self.approval_ref, self.perspective_ref)):
            raise ValueError("manual approval and perspective evidence are required")
        if self.source_mode not in {"development", "independent_review"}:
            raise ValueError("unsupported source_mode")
        object.__setattr__(self, "frames", tuple(self.frames))
        expected = tuple(range(start, end + 1, self.frame_step))
        if tuple(row.frame for row in self.frames) != expected:
            raise ValueError("missing, duplicated or out-of-order reviewed frames")
        if any(
            second.timestamp_seconds <= first.timestamp_seconds
            for first, second in zip(self.frames, self.frames[1:])
        ):
            raise ValueError("reviewed frame timestamps must strictly increase")


@dataclass(frozen=True)
class TurnCue:
    """Independent UI/hand-transition turn cue; never derived from focus ROI."""

    source_session: str
    stream_epoch: int
    frame: int
    actor: str
    method: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _source(self.source_session, self.stream_epoch)
        _frame(self.frame)
        if self.actor not in _ACTORS or self.method not in _TURN_METHODS:
            raise ValueError("unsupported actor or turn evidence method")
        if not self.evidence_refs or any(not ref for ref in self.evidence_refs):
            raise ValueError("independent turn evidence refs are required")
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


@dataclass(frozen=True)
class ContinuousFrameAudit:
    source_session: str
    source_sha256: str
    source_mode: str
    reviewed_frames: int
    focus_tp: int
    focus_fp: int
    focus_fn: int
    focus_tn: int
    focus_unknown_frames: int
    turn_correct: int
    turn_wrong: int
    turn_abstained: int
    turn_conflicted: int
    turn_truth_unknown: int
    event_tp: int
    event_fp: int
    event_fn: int
    actor_mismatches: int
    action_mismatches: int
    ambiguous_event_matches: int
    unknown_action_outputs: int
    unscored_action_outputs: int
    action_turn_disagreements: int

    def to_dict(self) -> dict[str, Any]:
        result = dict(self.__dict__)
        result["schema_version"] = "continuous_frame_actor_turn_audit_v0_1"
        result["development_audit_only"] = True
        result["formal_promotion_eligible"] = False
        result["safe_for_executor"] = False
        result["focus_precision"] = (
            self.focus_tp / (self.focus_tp + self.focus_fp)
            if self.focus_tp + self.focus_fp else None
        )
        result["focus_recall"] = (
            self.focus_tp / (self.focus_tp + self.focus_fn)
            if self.focus_tp + self.focus_fn else None
        )
        result["event_precision"] = (
            self.event_tp / (self.event_tp + self.event_fp)
            if self.event_tp + self.event_fp else None
        )
        result["event_recall"] = (
            self.event_tp / (self.event_tp + self.event_fn)
            if self.event_tp + self.event_fn else None
        )
        return result


def load_reviewed_segment(path: str | Path) -> ReviewedSegment:
    """Read signed manual truth, not a detector-generated annotation file."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or (
        payload.get("schema_version") != "continuous_frame_review_v0_1"
        or payload.get("approved") is not True
        or payload.get("manual_truth_source") != "raw_video_human_review"
    ):
        raise ValueError("continuous manual review is not approved or has wrong schema")
    frames = payload.get("frames")
    if not isinstance(frames, list):
        raise ValueError("review frames must be an array")
    return ReviewedSegment(
        source_session=payload["source_session"],
        source_sha256=payload["source_sha256"],
        stream_epoch=payload["stream_epoch"],
        start_frame=payload["start_frame"],
        end_frame=payload["end_frame"],
        frame_step=payload["frame_step"],
        approved_by=payload["approved_by"],
        approval_ref=payload["approval_ref"],
        perspective_ref=payload["perspective_ref"],
        source_mode=payload.get("source_mode", "development"),
        frames=tuple(ReviewedFrame(**row) for row in frames),
    )


def audit_continuous_segment(
    segment: ReviewedSegment,
    tracker_outputs: Sequence[CandidateTrackerOutput],
    actions: Sequence[ReconstructedAction],
    *,
    channel: CandidateChannel,
    output_source_sha256: str,
    turn_cues: Sequence[TurnCue] = (),
    maximum_action_lag_frames: int = 3,
) -> ContinuousFrameAudit:
    """Score scoped, reviewed *continuous* frames; never infer actor from ROI.

    Action evaluation is onset-based and permits only a small positive detector
    lag. UNKNOWN truth and machine abstentions are tracked separately. Wrong
    actor/kind is both a false positive and an unrecognized truth action.
    """
    if output_source_sha256 != segment.source_sha256:
        raise ValueError("tracker/action batch video SHA256 does not match review")
    if type(maximum_action_lag_frames) is not int or maximum_action_lag_frames < 0:
        raise ValueError("maximum_action_lag_frames must be nonnegative")
    if len(tracker_outputs) != len(segment.frames):
        raise ValueError("every reviewed frame needs one tracker output")
    frame_map = {row.frame: row for row in segment.frames}
    track_map: dict[int, CandidateTrackerOutput] = {}
    for row, output in zip(segment.frames, tracker_outputs):
        if (output.frame != row.frame or output.session != segment.source_session
                or output.stream_epoch != segment.stream_epoch):
            raise ValueError("tracker frames or capture scope differ from locked review")
        track_map[row.frame] = output

    cues_by_frame: dict[int, list[TurnCue]] = {}
    for cue in turn_cues:
        if (cue.source_session != segment.source_session
                or cue.stream_epoch != segment.stream_epoch
                or cue.frame not in frame_map):
            raise ValueError("turn cue scope or frame does not match review")
        cues_by_frame.setdefault(cue.frame, []).append(cue)

    focus_tp = focus_fp = focus_fn = focus_tn = focus_unknown = 0
    turn_correct = turn_wrong = turn_abstained = turn_conflicted = turn_truth_unknown = 0
    resolved_turn: dict[int, str | None] = {}
    for row in segment.frames:
        focus_seen = bool(tracks_for_channel(track_map[row.frame], channel))
        if row.focus == "UNKNOWN":
            focus_unknown += 1
        elif row.focus == "PRESENT":
            if focus_seen:
                focus_tp += 1
            else:
                focus_fn += 1
        elif focus_seen:
            focus_fp += 1
        else:
            focus_tn += 1

        cue_actors = {
            cue.actor for cue in cues_by_frame.get(row.frame, ())
            if cue.actor != "unknown"
        }
        if len(cue_actors) > 1:
            resolved_turn[row.frame] = None
            turn_conflicted += 1
        elif cue_actors:
            resolved_turn[row.frame] = next(iter(cue_actors))
        else:
            resolved_turn[row.frame] = None

        if row.turn_actor == "unknown":
            turn_truth_unknown += 1
        elif resolved_turn[row.frame] is None:
            turn_abstained += 1
        elif resolved_turn[row.frame] == row.turn_actor:
            turn_correct += 1
        else:
            turn_wrong += 1

    reviewed_events = [row for row in segment.frames if row.action in _EVENTS]
    consumed_truth: set[int] = set()
    event_tp = event_fp = actor_mismatches = action_mismatches = 0
    ambiguous = unknown_outputs = unscored_outputs = turn_disagreements = 0
    eligible: list[tuple[int, ReconstructedAction]] = []
    for action in actions:
        if action.kind.value not in _EVENTS | {
            "UNKNOWN_ACTION", "EVIDENCE_CONFLICT",
        }:
            continue
        details = action.details
        frame = details.get("frame")
        if (details.get("source_session") != segment.source_session
                or details.get("stream_epoch") != segment.stream_epoch
                or type(frame) is not int or frame not in frame_map):
            raise ValueError("action frame or capture scope differs from review")
        if details.get("source_sha256", segment.source_sha256) != segment.source_sha256:
            raise ValueError("action source SHA256 differs from review")
        if (action.kind.value not in _EVENTS
                or action.actor not in {"player", "opponent"}
                or action.evidence_grade == EvidenceGrade.UNKNOWN):
            unknown_outputs += 1
            continue
        eligible.append((frame, action))

    for frame, action in sorted(eligible, key=lambda item: item[0]):
        # UNKNOWN manual spans are not negatives; do not call their predictions FP.
        if frame_map[frame].action == "UNKNOWN":
            unscored_outputs += 1
            continue
        candidates = [
            row for row in reviewed_events
            if row.frame not in consumed_truth
            and 0 <= frame - row.frame <= maximum_action_lag_frames
        ]
        if not candidates:
            # A delayed prediction may fall inside an adjacent UNKNOWN truth span.
            if any(
                row.action == "UNKNOWN"
                and 0 <= frame - row.frame <= maximum_action_lag_frames
                for row in segment.frames
            ):
                unscored_outputs += 1
            else:
                event_fp += 1
            continue
        nearest_gap = min(frame - row.frame for row in candidates)
        nearest = [row for row in candidates if frame - row.frame == nearest_gap]
        if len(nearest) != 1:
            ambiguous += 1
            event_fp += 1
            continue
        truth = nearest[0]
        consumed_truth.add(truth.frame)
        if action.kind.value != truth.action:
            action_mismatches += 1
            event_fp += 1
        elif action.actor != truth.actor:
            actor_mismatches += 1
            event_fp += 1
        else:
            event_tp += 1
        turn_actor = resolved_turn.get(frame)
        if (action.kind == PublicActionKind.DISCARD
                and turn_actor is not None and action.actor != turn_actor):
            turn_disagreements += 1

    event_fn = len(reviewed_events) - event_tp
    return ContinuousFrameAudit(
        source_session=segment.source_session,
        source_sha256=segment.source_sha256,
        source_mode=segment.source_mode,
        reviewed_frames=len(segment.frames),
        focus_tp=focus_tp, focus_fp=focus_fp, focus_fn=focus_fn,
        focus_tn=focus_tn, focus_unknown_frames=focus_unknown,
        turn_correct=turn_correct, turn_wrong=turn_wrong,
        turn_abstained=turn_abstained, turn_conflicted=turn_conflicted,
        turn_truth_unknown=turn_truth_unknown,
        event_tp=event_tp, event_fp=event_fp, event_fn=event_fn,
        actor_mismatches=actor_mismatches, action_mismatches=action_mismatches,
        ambiguous_event_matches=ambiguous,
        unknown_action_outputs=unknown_outputs,
        unscored_action_outputs=unscored_outputs,
        action_turn_disagreements=turn_disagreements,
    )
