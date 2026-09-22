"""Temporal tracking for Public Tile Detector geometry candidates.

This module adds stability and identity-free track continuity on top of
public_tile_detector.py. It deliberately does not decide that a tracked
candidate is a discard, meld, river tile, or legal Mahjong action.

A caller may explicitly define a CandidateChannel and convert only that
channel's stable tracks into a RiverSnapshot. No default river ROI/profile is
embedded here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import hypot

from workspace.vision.public_observers import PublicTile, RiverSnapshot
from workspace.vision.public_tile_detector import (
    PublicGeometryCandidate,
    PublicGeometryFrame,
)


BBox = tuple[float, float, float, float]


class TrackEventKind(str, Enum):
    APPEARED = "APPEARED"
    DISAPPEARED = "DISAPPEARED"


@dataclass(frozen=True)
class StablePublicTrack:
    track_id: int
    geometry_kind: str
    normalized_bbox: BBox
    confidence: float
    first_seen_seconds: float
    last_seen_seconds: float
    evidence_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "track_id": self.track_id,
            "geometry_kind": self.geometry_kind,
            "normalized_bbox": list(self.normalized_bbox),
            "confidence": self.confidence,
            "first_seen_seconds": self.first_seen_seconds,
            "last_seen_seconds": self.last_seen_seconds,
            "evidence_refs": list(self.evidence_refs),
            "tile_id": "UNKNOWN",
        }


@dataclass(frozen=True)
class PublicTrackEvent:
    kind: TrackEventKind
    track: StablePublicTrack

    def to_dict(self) -> dict:
        return {"kind": self.kind.value, "track": self.track.to_dict()}


@dataclass(frozen=True)
class CandidateTrackerOutput:
    stable_tracks: tuple[StablePublicTrack, ...]
    events: tuple[PublicTrackEvent, ...]
    issues: tuple[str, ...]
    frame: str | int | None
    session: str | None
    stream_epoch: int
    safe_for_hint: bool = False
    safe_for_executor: bool = False

    def to_dict(self) -> dict:
        return {
            "schema_version": "public_candidate_tracker_v0_1",
            "stable_tracks": [track.to_dict() for track in self.stable_tracks],
            "events": [event.to_dict() for event in self.events],
            "issues": list(self.issues),
            "frame": self.frame,
            "session": self.session,
            "stream_epoch": self.stream_epoch,
            "safe_for_hint": False,
            "safe_for_executor": False,
        }


@dataclass(frozen=True)
class CandidateChannel:
    """Explicit semantic channel supplied by the caller.

    zones is optional. An empty zone tuple means all positions and is
    appropriate only when an upstream component already isolated the channel.

    A candidate passes a zone when at least minimum_zone_coverage of the
    candidate area overlaps one reviewed zone.
    """

    name: str
    geometry_kinds: tuple[str, ...]
    zones: tuple[BBox, ...] = ()
    minimum_zone_coverage: float = 0.5

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("channel name is required")
        if not self.geometry_kinds:
            raise ValueError("channel requires at least one geometry kind")
        if not 0 < self.minimum_zone_coverage <= 1:
            raise ValueError("minimum_zone_coverage must be within (0, 1]")
        for bbox in self.zones:
            _validate_bbox(bbox)

    def accepts(self, track: StablePublicTrack) -> bool:
        if track.geometry_kind not in self.geometry_kinds:
            return False
        if not self.zones:
            return True
        area = track.normalized_bbox[2] * track.normalized_bbox[3]
        if area <= 0:
            return False
        return any(
            _intersection(track.normalized_bbox, zone) / area
            >= self.minimum_zone_coverage
            for zone in self.zones
        )


@dataclass
class _TrackState:
    track_id: int
    candidate: PublicGeometryCandidate
    first_seen_seconds: float
    last_seen_seconds: float
    streak: int = 1
    missing_streak: int = 0
    confirmed: bool = False
    min_confidence: float = 1.0
    evidence_refs: list[str] = field(default_factory=list)


def _validate_bbox(bbox: BBox) -> BBox:
    if len(bbox) != 4:
        raise ValueError("bbox must contain x, y, width, height")
    x, y, width, height = (float(value) for value in bbox)
    if width <= 0 or height <= 0:
        raise ValueError("bbox width and height must be positive")
    if x < 0 or y < 0 or x + width > 1.000001 or y + height > 1.000001:
        raise ValueError("bbox must be normalized inside the frame")
    return (x, y, width, height)


def _centre(bbox: BBox) -> tuple[float, float]:
    return bbox[0] + bbox[2] / 2, bbox[1] + bbox[3] / 2


def _intersection(first: BBox, second: BBox) -> float:
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[0] + first[2], second[0] + second[2])
    bottom = min(first[1] + first[3], second[1] + second[3])
    return max(0.0, right - left) * max(0.0, bottom - top)


def _match_score(
    old: PublicGeometryCandidate,
    new: PublicGeometryCandidate,
) -> float | None:
    if old.geometry_kind != new.geometry_kind:
        return None

    old_box = old.normalized_bbox
    new_box = new.normalized_bbox
    old_width, old_height = old_box[2], old_box[3]
    new_width, new_height = new_box[2], new_box[3]
    width_ratio = max(old_width, new_width) / min(old_width, new_width)
    height_ratio = max(old_height, new_height) / min(old_height, new_height)
    if width_ratio > 1.40 or height_ratio > 1.40:
        return None

    average_width = (old_width + new_width) / 2
    average_height = (old_height + new_height) / 2
    old_centre = _centre(old_box)
    new_centre = _centre(new_box)
    dx = (old_centre[0] - new_centre[0]) / average_width
    dy = (old_centre[1] - new_centre[1]) / average_height
    distance = hypot(dx, dy)
    if distance > 0.75:
        return None

    overlap = _intersection(old_box, new_box)
    smaller_area = min(old_width * old_height, new_width * new_height)
    overlap_fraction = overlap / smaller_area if smaller_area > 0 else 0.0
    if overlap_fraction < 0.30 and distance > 0.35:
        return None

    return (
        distance
        + abs(width_ratio - 1)
        + abs(height_ratio - 1)
        + (1 - overlap_fraction) * 0.25
    )


def _frame_ref(frame: PublicGeometryFrame) -> str | None:
    if frame.frame is None:
        return None
    session = frame.session or "unknown"
    return f"public:{session}:frame:{frame.frame}"


def _snapshot(state: _TrackState) -> StablePublicTrack:
    return StablePublicTrack(
        track_id=state.track_id,
        geometry_kind=state.candidate.geometry_kind,
        normalized_bbox=state.candidate.normalized_bbox,
        confidence=round(state.min_confidence, 6),
        first_seen_seconds=state.first_seen_seconds,
        last_seen_seconds=state.last_seen_seconds,
        evidence_refs=tuple(state.evidence_refs),
    )


class PublicCandidateTracker:
    """Track geometry candidates across frames with fail-closed stability."""

    def __init__(
        self,
        *,
        settle_frames: int = 3,
        disappear_frames: int = 2,
        maximum_gap_seconds: float = 0.5,
    ):
        if settle_frames < 2:
            raise ValueError("settle_frames must be at least 2")
        if disappear_frames < 1:
            raise ValueError("disappear_frames must be at least 1")
        if maximum_gap_seconds <= 0:
            raise ValueError("maximum_gap_seconds must be positive")
        self.settle_frames = settle_frames
        self.disappear_frames = disappear_frames
        self.maximum_gap_seconds = float(maximum_gap_seconds)
        self._tracks: dict[int, _TrackState] = {}
        self._next_track_id = 1
        self._last_timestamp = 0.0
        self._seen_any = False
        self._session: str | None = None
        self._stream_epoch = 0

    def observe(
        self,
        frame: PublicGeometryFrame,
        *,
        timestamp_seconds: float,
    ) -> CandidateTrackerOutput:
        if timestamp_seconds < 0:
            raise ValueError("timestamp_seconds must be nonnegative")
        if self._seen_any and timestamp_seconds < self._last_timestamp:
            raise ValueError("tracker timestamps must be nondecreasing")

        issues: list[str] = []
        events: list[PublicTrackEvent] = []

        session_changed = (
            self._session is not None
            and frame.session is not None
            and frame.session != self._session
        )
        gap_reset = (
            self._seen_any
            and timestamp_seconds - self._last_timestamp > self.maximum_gap_seconds
        )
        if session_changed or gap_reset:
            self._tracks.clear()
            self._stream_epoch += 1
            if session_changed:
                issues.append("session_changed_reset")
            if gap_reset:
                issues.append("observation_gap_reset")

        self._seen_any = True
        self._last_timestamp = float(timestamp_seconds)
        if frame.session is not None:
            self._session = frame.session

        tracks = list(self._tracks.values())
        candidates = list(frame.candidates)
        scored: list[tuple[float, int, int]] = []
        for track_index, state in enumerate(tracks):
            for candidate_index, candidate in enumerate(candidates):
                score = _match_score(state.candidate, candidate)
                if score is not None:
                    scored.append((score, track_index, candidate_index))

        matched_tracks: set[int] = set()
        matched_candidates: set[int] = set()
        assignments: list[tuple[_TrackState, PublicGeometryCandidate]] = []
        for _, track_index, candidate_index in sorted(scored):
            state = tracks[track_index]
            if state.track_id in matched_tracks or candidate_index in matched_candidates:
                continue
            matched_tracks.add(state.track_id)
            matched_candidates.add(candidate_index)
            assignments.append((state, candidates[candidate_index]))

        ref = _frame_ref(frame)
        for state, candidate in assignments:
            state.candidate = candidate
            state.last_seen_seconds = float(timestamp_seconds)
            state.streak += 1
            state.missing_streak = 0
            state.min_confidence = min(state.min_confidence, candidate.confidence)
            if ref and ref not in state.evidence_refs:
                state.evidence_refs.append(ref)
            if not state.confirmed and state.streak >= self.settle_frames:
                state.confirmed = True
                events.append(
                    PublicTrackEvent(TrackEventKind.APPEARED, _snapshot(state))
                )

        remove_ids: list[int] = []
        for state in tracks:
            if state.track_id in matched_tracks:
                continue
            if not state.confirmed:
                remove_ids.append(state.track_id)
                continue
            state.missing_streak += 1
            if state.missing_streak >= self.disappear_frames:
                events.append(
                    PublicTrackEvent(TrackEventKind.DISAPPEARED, _snapshot(state))
                )
                remove_ids.append(state.track_id)

        for track_id in remove_ids:
            self._tracks.pop(track_id, None)

        for index, candidate in enumerate(candidates):
            if index in matched_candidates:
                continue
            state = _TrackState(
                track_id=self._next_track_id,
                candidate=candidate,
                first_seen_seconds=float(timestamp_seconds),
                last_seen_seconds=float(timestamp_seconds),
                min_confidence=candidate.confidence,
            )
            if ref:
                state.evidence_refs.append(ref)
            self._tracks[state.track_id] = state
            self._next_track_id += 1

        stable = tuple(
            _snapshot(state)
            for state in sorted(self._tracks.values(), key=lambda item: item.track_id)
            if state.confirmed
        )

        if frame.issues:
            issues.extend(f"detector:{issue}" for issue in frame.issues)
        if not stable:
            issues.append("no_stable_public_tracks")

        return CandidateTrackerOutput(
            stable_tracks=stable,
            events=tuple(events),
            issues=tuple(dict.fromkeys(issues)),
            frame=frame.frame,
            session=frame.session,
            stream_epoch=self._stream_epoch,
        )


def tracks_for_channel(
    output: CandidateTrackerOutput,
    channel: CandidateChannel,
) -> tuple[StablePublicTrack, ...]:
    return tuple(track for track in output.stable_tracks if channel.accepts(track))


def river_snapshot_from_channel(
    output: CandidateTrackerOutput,
    *,
    channel: CandidateChannel,
    actor: str,
    timestamp_seconds: float,
) -> RiverSnapshot:
    """Convert an explicitly selected stable channel into a RiverSnapshot."""
    selected = tracks_for_channel(output, channel)
    refs: list[str] = []
    tiles: list[PublicTile] = []
    for track in selected:
        for ref in track.evidence_refs:
            if ref not in refs:
                refs.append(ref)
        tiles.append(
            PublicTile(
                normalized_bbox=track.normalized_bbox,
                tile_id=None,
                confidence=track.confidence,
                evidence_refs=track.evidence_refs,
            )
        )

    return RiverSnapshot(
        timestamp_seconds=timestamp_seconds,
        actor=actor,
        tiles=tuple(tiles),
        frame=output.frame,
        trusted=True,
        evidence_refs=tuple(refs),
        stream_epoch=output.stream_epoch,
    )
