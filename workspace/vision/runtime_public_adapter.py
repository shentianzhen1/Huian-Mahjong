"""Bridge Runtime Vision V0.2 reports into public observer snapshots.

This adapter intentionally uses only data already emitted by the read-only
runtime reader. It does not add new pixel assumptions, does not classify meld
identities with concealed-hand templates, and never changes Rules or Executor.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from statistics import median
from typing import Any, Iterable

from workspace.vision.public_match_reconstruction import ObservationKind, RawObservation
from workspace.vision.public_observers import MeldGroup, MeldSnapshot


def _bbox(item: dict[str, Any]) -> tuple[float, float, float, float]:
    raw = item.get("normalized_bbox")
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        raise ValueError("runtime component is missing normalized_bbox")
    return tuple(float(value) for value in raw)  # type: ignore[return-value]


def _component_confidence(item: dict[str, Any]) -> float:
    value = item.get("confidence", 0.0)
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, result))


def _identity(item: dict[str, Any]) -> str | None:
    value = item.get("tile_id")
    if not value or value == "UNKNOWN":
        return None
    return str(value)


def _centre_y(box: tuple[float, float, float, float]) -> float:
    return box[1] + box[3] / 2


def _right(box: tuple[float, float, float, float]) -> float:
    return box[0] + box[2]


def _union_bbox(
    boxes: Iterable[tuple[float, float, float, float]]
) -> tuple[float, float, float, float]:
    boxes = tuple(boxes)
    if not boxes:
        raise ValueError("cannot union empty bbox sequence")
    left = min(box[0] for box in boxes)
    top = min(box[1] for box in boxes)
    right = max(box[0] + box[2] for box in boxes)
    bottom = max(box[1] + box[3] for box in boxes)
    return (left, top, right - left, bottom - top)


def _runtime_refs(report: dict[str, Any], components: Iterable[dict[str, Any]] = ()) -> tuple[str, ...]:
    refs: list[str] = []
    session = report.get("session") or "unknown"
    for component in components:
        frame = component.get("frame")
        if frame is not None:
            ref = f"runtime:{session}:frame:{frame}"
            if ref not in refs:
                refs.append(ref)
    if not refs:
        for frame in report.get("frames") or ():
            ref = f"runtime:{session}:frame:{frame}"
            if ref not in refs:
                refs.append(ref)
    return tuple(refs)


def _cluster_meld_components(
    components: list[dict[str, Any]]
) -> list[list[dict[str, Any]]]:
    """Re-group flattened meld components using only local geometry.

    Dynamic geometry already labels individual components as meld candidates
    but currently flattens group membership. This recovers local groups without
    assuming absolute screen position or left/right semantic order.
    """
    if not components:
        return []
    ordered = sorted(components, key=lambda item: (_bbox(item)[0], _bbox(item)[1]))
    widths = [_bbox(item)[2] for item in ordered]
    heights = [_bbox(item)[3] for item in ordered]
    typical_width = median(widths)
    typical_height = median(heights)

    groups: list[list[dict[str, Any]]] = [[ordered[0]]]
    for item in ordered[1:]:
        box = _bbox(item)
        group = groups[-1]
        group_boxes = [_bbox(member) for member in group]
        group_right = max(_right(member) for member in group_boxes)
        group_centre_y = median(_centre_y(member) for member in group_boxes)
        gap = box[0] - group_right
        y_delta = abs(_centre_y(box) - group_centre_y)

        # Overlap is expected in the reviewed 3+1 stacked meld layout.
        close_horizontally = gap <= typical_width * 1.20
        close_vertically = y_delta <= typical_height * 0.80
        if close_horizontally and close_vertically and len(group) < 4:
            group.append(item)
        else:
            groups.append([item])
    return groups


def player_meld_snapshot_from_runtime(
    report: dict[str, Any],
    *,
    timestamp_seconds: float,
) -> MeldSnapshot:
    """Convert one stable runtime report into a player-side MeldSnapshot.

    Runtime V0.2 currently does not classify meld components with an
    independently validated meld-region identity model. Therefore identities
    remain None unless a future runtime report explicitly emits trusted
    tile_id values for those components.
    """
    components = [
        item for item in report.get("components", ())
        if item.get("region_candidate") == "meld"
    ]
    trusted = not bool(report.get("geometry_untrusted"))
    if not trusted:
        components = []

    groups: list[MeldGroup] = []
    for cluster in _cluster_meld_components(components):
        if len(cluster) not in {3, 4}:
            # Keep the snapshot trusted at the report level, but do not turn an
            # incomplete geometric cluster into a semantic meld group.
            continue
        boxes = [_bbox(item) for item in cluster]
        groups.append(
            MeldGroup(
                normalized_bbox=_union_bbox(boxes),
                tiles=tuple(_identity(item) for item in cluster),
                confidence=min(_component_confidence(item) for item in cluster),
                evidence_refs=_runtime_refs(report, cluster),
            )
        )

    return MeldSnapshot(
        timestamp_seconds=timestamp_seconds,
        actor="player",
        groups=tuple(groups),
        frame=(report.get("frames") or [None])[-1],
        trusted=trusted,
        evidence_refs=_runtime_refs(report, components),
        source_session=report.get("session") or None,
        stream_epoch=report.get("stream_epoch", 0),
    )


def _concealed_components(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item for item in report.get("components", ())
        if item.get("region_candidate") in {"hand", "draw_visual"}
    ]


def _tile_counter(components: Iterable[dict[str, Any]]) -> Counter[str]:
    result: Counter[str] = Counter()
    for item in components:
        tile_id = _identity(item)
        if tile_id is not None:
            result[tile_id] += 1
    return result


def _expand_counter(counter: Counter[str]) -> tuple[str, ...]:
    values: list[str] = []
    for tile_id in sorted(counter):
        values.extend([tile_id] * counter[tile_id])
    return tuple(values)


def player_hand_delta_from_runtime(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    timestamp_seconds: float,
) -> RawObservation | None:
    """Compare two stable runtime reports and emit a player HAND_DELTA.

    This function observes a visible concealed-hand delta; it does not decide
    whether the cause was a claim, discard, flower replacement, kong, or other
    game action. Temporal action assembly remains a separate layer.
    """
    if before.get("geometry_untrusted") or after.get("geometry_untrusted"):
        return None

    # Never compare two reports from distinct sources or tracking epochs.
    before_session, after_session = before.get("session"), after.get("session")
    before_epoch = before.get("stream_epoch", 0)
    after_epoch = after.get("stream_epoch", 0)
    if before_session != after_session or before_epoch != after_epoch:
        return None
    if isinstance(before_epoch, bool) or not isinstance(before_epoch, int) or before_epoch < 0:
        return None

    before_count = before.get("concealed_tile_count")
    after_count = after.get("concealed_tile_count")
    if not isinstance(before_count, int) or not isinstance(after_count, int):
        return None
    if before_count == after_count:
        return None

    removed_count = max(0, before_count - after_count)
    added_count = max(0, after_count - before_count)
    details: dict[str, Any] = {
        "removed_count": removed_count,
        "added_count": added_count,
        "before_concealed_count": before_count,
        "after_concealed_count": after_count,
        "observer": "runtime_public_adapter_v0_1",
        "identity_delta_observed": False,
        "source_session": before_session,
        "stream_epoch": before_epoch,
    }

    before_components = _concealed_components(before)
    after_components = _concealed_components(after)
    exact_identity_available = bool(
        before.get("all_concealed_tile_ids_trusted")
        and after.get("all_concealed_tile_ids_trusted")
    )
    if exact_identity_available:
        before_tiles = _tile_counter(before_components)
        after_tiles = _tile_counter(after_components)
        removed = before_tiles - after_tiles
        added = after_tiles - before_tiles
        if sum(removed.values()) == removed_count and sum(added.values()) == added_count:
            details["removed_tiles"] = list(_expand_counter(removed))
            details["added_tiles"] = list(_expand_counter(added))
            details["identity_delta_observed"] = True

    confidences = [
        _component_confidence(item)
        for item in (*before_components, *after_components)
    ]
    confidence = min(confidences) if confidences else 0.0
    refs = []
    for ref in (*_runtime_refs(before, before_components), *_runtime_refs(after, after_components)):
        if ref not in refs:
            refs.append(ref)

    return RawObservation(
        timestamp_seconds=timestamp_seconds,
        actor="player",
        kind=ObservationKind.HAND_DELTA,
        confidence=confidence,
        evidence_refs=tuple(refs),
        details=details,
    )
