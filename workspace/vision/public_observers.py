"""Stable, geometry-first public discard and meld observers.

These observers sit between pixel/identity detectors and public action
reconstruction. They deliberately avoid fixed river growth direction, fixed
meld ordering, and Mahjong-rule legality. They only compare stable public
snapshots and emit UNKNOWN-friendly RawObservation facts.

All outputs are read-only and never drive Executor.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Iterable, Sequence

from workspace.vision.public_match_reconstruction import ObservationKind, RawObservation


BBox = tuple[float, float, float, float]


def _validate_bbox(bbox: BBox) -> BBox:
    if len(bbox) != 4:
        raise ValueError("bbox must contain x, y, width, height")
    x, y, width, height = (float(value) for value in bbox)
    if width <= 0 or height <= 0:
        raise ValueError("bbox width and height must be positive")
    if x < 0 or y < 0 or x + width > 1.000001 or y + height > 1.000001:
        raise ValueError("bbox must be normalized inside the frame")
    return (x, y, width, height)


def _validate_actor(actor: str) -> None:
    if actor not in {"player", "opponent"}:
        raise ValueError("public observer actor must be player or opponent")


def _validate_confidence(confidence: float) -> float:
    value = float(confidence)
    if not 0 <= value <= 1:
        raise ValueError("confidence must be between 0 and 1")
    return value


def _merge_refs(items: Iterable[Sequence[str]]) -> tuple[str, ...]:
    refs: list[str] = []
    for group in items:
        for ref in group:
            if ref and ref not in refs:
                refs.append(ref)
    return tuple(refs)


def _centre(bbox: BBox) -> tuple[float, float]:
    x, y, width, height = bbox
    return x + width / 2, y + height / 2


def _bbox_match_score(first: BBox, second: BBox) -> float | None:
    """Return a geometry match cost or None when boxes are incompatible.

    The tolerance is relative to local tile/group size, not absolute screen
    position. This allows small replay jitter without assuming river direction
    or meld ordering.
    """
    first_centre = _centre(first)
    second_centre = _centre(second)
    average_width = (first[2] + second[2]) / 2
    average_height = (first[3] + second[3]) / 2
    if average_width <= 0 or average_height <= 0:
        return None

    width_ratio = max(first[2], second[2]) / min(first[2], second[2])
    height_ratio = max(first[3], second[3]) / min(first[3], second[3])
    if width_ratio > 1.35 or height_ratio > 1.35:
        return None

    dx = (first_centre[0] - second_centre[0]) / average_width
    dy = (first_centre[1] - second_centre[1]) / average_height
    distance = hypot(dx, dy)
    if distance > 0.65:
        return None
    return distance + abs(width_ratio - 1) + abs(height_ratio - 1)


def _identity_compatible(first: str | None, second: str | None) -> bool:
    # Unknown identity never contradicts geometry. It also never upgrades the
    # later public action to a known tile by itself.
    return first is None or second is None or first == second


@dataclass(frozen=True)
class PublicTile:
    normalized_bbox: BBox
    tile_id: str | None = None
    confidence: float = 1.0
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "normalized_bbox", _validate_bbox(self.normalized_bbox))
        object.__setattr__(self, "confidence", _validate_confidence(self.confidence))
        if self.tile_id == "":
            raise ValueError("tile_id cannot be empty")
        object.__setattr__(
            self,
            "evidence_refs",
            tuple(str(ref) for ref in self.evidence_refs if str(ref)),
        )


@dataclass(frozen=True)
class RiverSnapshot:
    timestamp_seconds: float
    actor: str
    tiles: tuple[PublicTile, ...]
    frame: str | int | None = None
    trusted: bool = True
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.timestamp_seconds < 0:
            raise ValueError("timestamp_seconds must be nonnegative")
        _validate_actor(self.actor)
        object.__setattr__(self, "tiles", tuple(self.tiles))
        object.__setattr__(
            self,
            "evidence_refs",
            tuple(str(ref) for ref in self.evidence_refs if str(ref)),
        )


@dataclass(frozen=True)
class MeldGroup:
    normalized_bbox: BBox
    tiles: tuple[str | None, ...]
    confidence: float = 1.0
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "normalized_bbox", _validate_bbox(self.normalized_bbox))
        if len(self.tiles) not in {3, 4}:
            raise ValueError("meld group must expose 3 or 4 tile faces")
        if any(tile == "" for tile in self.tiles):
            raise ValueError("meld tile identity cannot be empty")
        object.__setattr__(self, "tiles", tuple(self.tiles))
        object.__setattr__(self, "confidence", _validate_confidence(self.confidence))
        object.__setattr__(
            self,
            "evidence_refs",
            tuple(str(ref) for ref in self.evidence_refs if str(ref)),
        )

    @property
    def identities_complete(self) -> bool:
        return all(tile is not None for tile in self.tiles)

    @property
    def known_tiles(self) -> tuple[str, ...]:
        return tuple(tile for tile in self.tiles if tile is not None)


@dataclass(frozen=True)
class MeldSnapshot:
    timestamp_seconds: float
    actor: str
    groups: tuple[MeldGroup, ...]
    frame: str | int | None = None
    trusted: bool = True
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.timestamp_seconds < 0:
            raise ValueError("timestamp_seconds must be nonnegative")
        _validate_actor(self.actor)
        object.__setattr__(self, "groups", tuple(self.groups))
        object.__setattr__(
            self,
            "evidence_refs",
            tuple(str(ref) for ref in self.evidence_refs if str(ref)),
        )


@dataclass(frozen=True)
class ObserverOutput:
    observation: RawObservation | None
    stable: bool
    trusted: bool
    issues: tuple[str, ...] = ()
    baseline_rebased: bool = False


def _match_tiles(
    previous: Sequence[PublicTile],
    current: Sequence[PublicTile],
) -> tuple[dict[int, int], tuple[int, ...], tuple[int, ...]]:
    candidates: list[tuple[float, int, int]] = []
    for previous_index, old in enumerate(previous):
        for current_index, new in enumerate(current):
            score = _bbox_match_score(old.normalized_bbox, new.normalized_bbox)
            if score is None or not _identity_compatible(old.tile_id, new.tile_id):
                continue
            candidates.append((score, previous_index, current_index))

    matches: dict[int, int] = {}
    used_current: set[int] = set()
    for _, previous_index, current_index in sorted(candidates):
        if previous_index in matches or current_index in used_current:
            continue
        matches[previous_index] = current_index
        used_current.add(current_index)

    unmatched_previous = tuple(
        index for index in range(len(previous)) if index not in matches
    )
    unmatched_current = tuple(
        index for index in range(len(current)) if index not in used_current
    )
    return matches, unmatched_previous, unmatched_current


def _partial_multiset_compatible(
    first: tuple[str | None, ...],
    second: tuple[str | None, ...],
) -> bool:
    """Compare visible meld identities without assuming display ordering."""
    if len(first) != len(second):
        return False
    first_unknown = sum(tile is None for tile in first)
    second_unknown = sum(tile is None for tile in second)
    first_known: dict[str, int] = {}
    second_known: dict[str, int] = {}
    for tile in first:
        if tile is not None:
            first_known[tile] = first_known.get(tile, 0) + 1
    for tile in second:
        if tile is not None:
            second_known[tile] = second_known.get(tile, 0) + 1

    for tile in set(first_known) | set(second_known):
        if first_known.get(tile, 0) > second_known.get(tile, 0) + second_unknown:
            return False
        if second_known.get(tile, 0) > first_known.get(tile, 0) + first_unknown:
            return False
    return True


def _group_identity_compatible(first: MeldGroup, second: MeldGroup) -> bool:
    if len(first.tiles) == len(second.tiles):
        return _partial_multiset_compatible(first.tiles, second.tiles)
    # A 3 -> 4 transition may be ADD_KONG. Geometry decides candidate group
    # continuity; exact semantic classification remains the reconstructor's job.
    return {len(first.tiles), len(second.tiles)} == {3, 4}


def _match_groups(
    previous: Sequence[MeldGroup],
    current: Sequence[MeldGroup],
) -> tuple[dict[int, int], tuple[int, ...], tuple[int, ...]]:
    candidates: list[tuple[float, int, int]] = []
    for previous_index, old in enumerate(previous):
        for current_index, new in enumerate(current):
            score = _bbox_match_score(old.normalized_bbox, new.normalized_bbox)
            if score is None or not _group_identity_compatible(old, new):
                continue
            candidates.append((score, previous_index, current_index))

    matches: dict[int, int] = {}
    used_current: set[int] = set()
    for _, previous_index, current_index in sorted(candidates):
        if previous_index in matches or current_index in used_current:
            continue
        matches[previous_index] = current_index
        used_current.add(current_index)

    unmatched_previous = tuple(
        index for index in range(len(previous)) if index not in matches
    )
    unmatched_current = tuple(
        index for index in range(len(current)) if index not in used_current
    )
    return matches, unmatched_previous, unmatched_current


def _river_equivalent(first: RiverSnapshot, second: RiverSnapshot) -> bool:
    if first.actor != second.actor or len(first.tiles) != len(second.tiles):
        return False
    matches, unmatched_first, unmatched_second = _match_tiles(first.tiles, second.tiles)
    return (
        len(matches) == len(first.tiles)
        and not unmatched_first
        and not unmatched_second
    )


def _meld_equivalent(first: MeldSnapshot, second: MeldSnapshot) -> bool:
    if first.actor != second.actor or len(first.groups) != len(second.groups):
        return False
    matches, unmatched_first, unmatched_second = _match_groups(first.groups, second.groups)
    if unmatched_first or unmatched_second or len(matches) != len(first.groups):
        return False
    for old_index, new_index in matches.items():
        old = first.groups[old_index]
        new = second.groups[new_index]
        if len(old.tiles) != len(new.tiles):
            return False
        if not _partial_multiset_compatible(old.tiles, new.tiles):
            return False
    return True


class DiscardRiverObserver:
    """Turn stable river snapshot changes into one public DISCARD observation.

    No river growth direction, wrap direction, or fixed slot coordinates are
    assumed. A discard is emitted only when all previous public tiles have a
    geometry match and exactly one current tile is unmatched.
    """

    def __init__(self, settle_frames: int = 3):
        if settle_frames < 2:
            raise ValueError("settle_frames must be at least 2")
        self.settle_frames = settle_frames
        self._accepted: RiverSnapshot | None = None
        self._pending: RiverSnapshot | None = None
        self._pending_streak = 0

    def observe(self, snapshot: RiverSnapshot) -> ObserverOutput:
        if not snapshot.trusted:
            self._clear_pending()
            return ObserverOutput(
                observation=None,
                stable=False,
                trusted=False,
                issues=("river_snapshot_untrusted",),
            )
        if self._accepted is not None and snapshot.actor != self._accepted.actor:
            self._clear_pending()
            return ObserverOutput(
                observation=None,
                stable=False,
                trusted=False,
                issues=("river_actor_changed",),
            )

        if self._pending is None or not _river_equivalent(self._pending, snapshot):
            self._pending = snapshot
            self._pending_streak = 1
            return ObserverOutput(None, stable=False, trusted=True)

        self._pending = snapshot
        self._pending_streak += 1
        if self._pending_streak < self.settle_frames:
            return ObserverOutput(None, stable=False, trusted=True)

        stable_snapshot = self._pending
        self._clear_pending()

        if self._accepted is None:
            self._accepted = stable_snapshot
            return ObserverOutput(
                observation=None,
                stable=True,
                trusted=True,
                issues=("river_baseline_established",),
            )

        previous = self._accepted
        matches, unmatched_previous, unmatched_current = _match_tiles(
            previous.tiles,
            stable_snapshot.tiles,
        )

        if (
            len(stable_snapshot.tiles) == len(previous.tiles) + 1
            and not unmatched_previous
            and len(unmatched_current) == 1
            and len(matches) == len(previous.tiles)
        ):
            new_tile = stable_snapshot.tiles[unmatched_current[0]]
            refs = _merge_refs(
                [
                    previous.evidence_refs,
                    stable_snapshot.evidence_refs,
                    new_tile.evidence_refs,
                ]
            )
            observation = RawObservation(
                timestamp_seconds=stable_snapshot.timestamp_seconds,
                actor=stable_snapshot.actor,
                kind=ObservationKind.DISCARD,
                tile=new_tile.tile_id,
                confidence=new_tile.confidence,
                evidence_refs=refs,
                details={
                    "frame": stable_snapshot.frame,
                    "previous_river_count": len(previous.tiles),
                    "current_river_count": len(stable_snapshot.tiles),
                    "new_tile_bbox": list(new_tile.normalized_bbox),
                    "tile_identity_observed": new_tile.tile_id is not None,
                    "observer": "discard_river_v0_1",
                },
            )
            self._accepted = stable_snapshot
            return ObserverOutput(
                observation=observation,
                stable=True,
                trusted=True,
            )

        # Same geometry/count after a stable identity refresh is not an event.
        if (
            len(stable_snapshot.tiles) == len(previous.tiles)
            and not unmatched_previous
            and not unmatched_current
        ):
            self._accepted = stable_snapshot
            return ObserverOutput(None, stable=True, trusted=True)

        # A claimed discard may disappear from the river. The visual change is
        # real, but it is not sufficient by itself to classify CHI/PENG/KONG.
        if (
            len(stable_snapshot.tiles) < len(previous.tiles)
            and len(unmatched_current) == 0
        ):
            self._accepted = stable_snapshot
            return ObserverOutput(
                observation=None,
                stable=True,
                trusted=True,
                issues=("river_tile_removed_or_claimed",),
                baseline_rebased=True,
            )

        # Missed frames or a layout transition can expose multiple unmatched
        # tiles. Rebase so later events remain observable, but never invent the
        # missing discard sequence.
        self._accepted = stable_snapshot
        return ObserverOutput(
            observation=None,
            stable=True,
            trusted=False,
            issues=("river_transition_ambiguous",),
            baseline_rebased=True,
        )

    def _clear_pending(self) -> None:
        self._pending = None
        self._pending_streak = 0


class MeldSnapshotObserver:
    """Turn stable exposed-meld snapshot changes into MELD_DELTA observations."""

    def __init__(self, settle_frames: int = 3):
        if settle_frames < 2:
            raise ValueError("settle_frames must be at least 2")
        self.settle_frames = settle_frames
        self._accepted: MeldSnapshot | None = None
        self._pending: MeldSnapshot | None = None
        self._pending_streak = 0

    def observe(self, snapshot: MeldSnapshot) -> ObserverOutput:
        if not snapshot.trusted:
            self._clear_pending()
            return ObserverOutput(
                observation=None,
                stable=False,
                trusted=False,
                issues=("meld_snapshot_untrusted",),
            )
        if self._accepted is not None and snapshot.actor != self._accepted.actor:
            self._clear_pending()
            return ObserverOutput(
                observation=None,
                stable=False,
                trusted=False,
                issues=("meld_actor_changed",),
            )

        if self._pending is None or not _meld_equivalent(self._pending, snapshot):
            self._pending = snapshot
            self._pending_streak = 1
            return ObserverOutput(None, stable=False, trusted=True)

        self._pending = snapshot
        self._pending_streak += 1
        if self._pending_streak < self.settle_frames:
            return ObserverOutput(None, stable=False, trusted=True)

        stable_snapshot = self._pending
        self._clear_pending()

        if self._accepted is None:
            self._accepted = stable_snapshot
            return ObserverOutput(
                observation=None,
                stable=True,
                trusted=True,
                issues=("meld_baseline_established",),
            )

        previous = self._accepted
        matches, unmatched_previous, unmatched_current = _match_groups(
            previous.groups,
            stable_snapshot.groups,
        )

        changed_pairs: list[tuple[MeldGroup, MeldGroup]] = []
        for old_index, new_index in matches.items():
            old = previous.groups[old_index]
            new = stable_snapshot.groups[new_index]
            if len(old.tiles) != len(new.tiles):
                changed_pairs.append((old, new))

        if (
            not unmatched_previous
            and len(unmatched_current) == 1
            and not changed_pairs
        ):
            new_group = stable_snapshot.groups[unmatched_current[0]]
            observation = self._group_observation(
                stable_snapshot,
                new_group,
                previous_group=None,
            )
            self._accepted = stable_snapshot
            issues = () if new_group.identities_complete else ("meld_identity_incomplete",)
            return ObserverOutput(observation, True, True, issues=issues)

        if (
            not unmatched_previous
            and not unmatched_current
            and len(changed_pairs) == 1
        ):
            old_group, new_group = changed_pairs[0]
            if len(old_group.tiles) == 3 and len(new_group.tiles) == 4:
                observation = self._group_observation(
                    stable_snapshot,
                    new_group,
                    previous_group=old_group,
                )
                self._accepted = stable_snapshot
                issues = () if (
                    old_group.identities_complete and new_group.identities_complete
                ) else ("meld_identity_incomplete",)
                return ObserverOutput(observation, True, True, issues=issues)

        if (
            len(stable_snapshot.groups) == len(previous.groups)
            and not unmatched_previous
            and not unmatched_current
            and not changed_pairs
        ):
            self._accepted = stable_snapshot
            return ObserverOutput(None, True, True)

        self._accepted = stable_snapshot
        return ObserverOutput(
            observation=None,
            stable=True,
            trusted=False,
            issues=("meld_transition_ambiguous",),
            baseline_rebased=True,
        )

    @staticmethod
    def _group_observation(
        snapshot: MeldSnapshot,
        group: MeldGroup,
        *,
        previous_group: MeldGroup | None,
    ) -> RawObservation:
        identities_complete = group.identities_complete
        refs = _merge_refs(
            [
                snapshot.evidence_refs,
                group.evidence_refs,
                previous_group.evidence_refs if previous_group else (),
            ]
        )
        details: dict[str, object] = {
            "frame": snapshot.frame,
            "group_bbox": list(group.normalized_bbox),
            "group_size": len(group.tiles),
            "tile_identity_complete": identities_complete,
            "tile_candidates": [tile for tile in group.tiles],
            "observer": "meld_snapshot_v0_1",
        }
        if previous_group is not None:
            details["previous_group_size"] = len(previous_group.tiles)
            details["previous_meld"] = (
                list(previous_group.known_tiles)
                if previous_group.identities_complete
                else []
            )

        return RawObservation(
            timestamp_seconds=snapshot.timestamp_seconds,
            actor=snapshot.actor,
            kind=ObservationKind.MELD_DELTA,
            confidence=group.confidence,
            tiles=group.known_tiles if identities_complete else (),
            evidence_refs=refs,
            details=details,
        )

    def _clear_pending(self) -> None:
        self._pending = None
        self._pending_streak = 0
