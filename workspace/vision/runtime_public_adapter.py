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

from workspace.vision.current_state_snapshot import CurrentTableSnapshot
from workspace.vision.public_match_reconstruction import ObservationKind, RawObservation
from workspace.vision.public_observers import (
    MeldGroup,
    MeldSnapshot,
    RiverSnapshot,
)


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


def _trusted_gold_from_runtime(
    report: dict[str, Any],
    gold_components: list[dict[str, Any]],
    *,
    geometry_trusted: bool,
    issues: list[str],
) -> tuple[str | None, bool]:
    """Require independent same-identity Gold reads from at least two frames.

    Runtime burst geometry stability is not proof of tile identity stability.
    Only explicit per-frame Gold classifications emitted by Runtime Vision may
    promote a Gold tile into the current-table snapshot. Hidden dice, wall
    positions, random seeds or any other opening inference are intentionally
    ignored by this adapter.
    """
    if not geometry_trusted:
        return None, False
    if len(gold_components) != 1:
        issues.append("runtime_gold_component_conflict")
        return None, False

    observations = report.get("gold_identity_observations")
    if not isinstance(observations, list) or not observations:
        issues.append("runtime_gold_multiframe_evidence_missing")
        return None, False
    if not all(isinstance(item, dict) for item in observations):
        issues.append("runtime_gold_multiframe_evidence_invalid")
        return None, False

    report_frames = report.get("frames")
    allowed_frames = set(report_frames) if isinstance(report_frames, (list, tuple)) else set()
    observed_frames = [item.get("frame") for item in observations]
    if (
        any(frame is None for frame in observed_frames)
        or any(frame not in allowed_frames for frame in observed_frames)
        or len(set(observed_frames)) < 2
    ):
        issues.append("runtime_gold_frame_scope_conflict")
        return None, False

    identities = [_identity(item) for item in observations]
    known_identities = {tile_id for tile_id in identities if tile_id is not None}
    if len(known_identities) > 1:
        issues.append("runtime_gold_identity_conflict")
        return None, False
    if (
        not identities
        or any(tile_id is None for tile_id in identities)
        or any(item.get("identity_reason") != "accepted" for item in observations)
    ):
        issues.append("runtime_gold_frame_identity_untrusted")
        return None, False

    gold_tile = identities[0]
    if gold_tile is None or any(tile_id != gold_tile for tile_id in identities):
        issues.append("runtime_gold_identity_conflict")
        return None, False

    chosen = gold_components[0]
    if _identity(chosen) != gold_tile or chosen.get("identity_reason") != "accepted":
        issues.append("runtime_gold_fused_identity_conflict")
        return None, False
    return gold_tile, True


def _meld_identity(item: dict[str, Any]) -> str | None:
    """Accept only identities produced by the strict read-only public-meld gate."""
    result = item.get("public_identity_result")
    if not isinstance(result, dict):
        return None
    tile_id = result.get("read_only_runtime_candidate")
    if (
        not isinstance(tile_id, str)
        or not tile_id
        or result.get("region") != "public_meld"
        or result.get("safe_for_runtime") is not True
        or result.get("safe_for_executor") is not False
        or result.get("formal_promotion_evidence") is not False
        or result.get("winner_independent_match_groups", 0) < 2
        or result.get("eligible_class_count", 0) < 2
    ):
        return None
    try:
        score = float(result.get("score"))
        margin = float(result.get("margin"))
    except (TypeError, ValueError):
        return None
    if score < 0.93 or margin < 0.075:
        return None
    return tile_id


def _snapshot_scope_matches(
    snapshot: RiverSnapshot | MeldSnapshot,
    *,
    source_session: str | None,
    stream_epoch: int,
) -> bool:
    return (
        bool(source_session)
        and snapshot.source_session == source_session
        and snapshot.stream_epoch == stream_epoch
    )


def _river_values(
    snapshot: RiverSnapshot | None,
    *,
    actor: str,
    source_session: str | None,
    stream_epoch: int,
    issues: list[str],
) -> tuple[tuple[str | None, ...], bool]:
    if snapshot is None:
        issues.append(f"{actor}_river_missing")
        return (), False
    if snapshot.actor != actor:
        issues.append(f"{actor}_river_actor_conflict")
        return (), False
    if not _snapshot_scope_matches(
        snapshot,
        source_session=source_session,
        stream_epoch=stream_epoch,
    ):
        issues.append(f"{actor}_river_source_conflict")
        return (), False
    return tuple(tile.tile_id for tile in snapshot.tiles), snapshot.trusted


def _meld_values(
    snapshot: MeldSnapshot | None,
    *,
    actor: str,
    source_session: str | None,
    stream_epoch: int,
    issues: list[str],
) -> tuple[tuple[tuple[str | None, ...], ...], bool]:
    if snapshot is None:
        issues.append(f"{actor}_meld_missing")
        return (), False
    if snapshot.actor != actor:
        issues.append(f"{actor}_meld_actor_conflict")
        return (), False
    if not _snapshot_scope_matches(
        snapshot,
        source_session=source_session,
        stream_epoch=stream_epoch,
    ):
        issues.append(f"{actor}_meld_source_conflict")
        return (), False
    return tuple(group.tiles for group in snapshot.groups), snapshot.trusted


def current_snapshot_from_runtime(
    report: dict[str, Any],
    *,
    timestamp_seconds: float,
    player_river: RiverSnapshot | None = None,
    opponent_river: RiverSnapshot | None = None,
    opponent_meld: MeldSnapshot | None = None,
) -> CurrentTableSnapshot:
    """Convert one Runtime burst and optional public observers into a snapshot.

    The player hand, opened Gold and player meld count come only from the same
    Runtime report.  Optional public observations are accepted only when actor,
    source session and stream epoch match.  Mismatched inputs are dropped rather
    than joined across recordings.
    """
    if not isinstance(report, dict):
        raise TypeError("report must be a dictionary")
    source_session = report.get("session")
    stream_epoch = report.get("stream_epoch", 0)
    if isinstance(stream_epoch, bool) or not isinstance(stream_epoch, int):
        stream_epoch = -1

    issues: list[str] = []
    geometry_trusted = not bool(report.get("geometry_untrusted", True))
    components = report.get("components")
    if not isinstance(components, list):
        components = []
        issues.append("runtime_components_missing")

    concealed = [
        item
        for item in components
        if isinstance(item, dict)
        and item.get("region_candidate") in {"hand", "draw_visual"}
    ]
    own_hand = tuple(_identity(item) for item in concealed)
    declared_count = report.get("concealed_tile_count")
    hand_trusted = bool(
        geometry_trusted
        and report.get("all_concealed_tile_ids_trusted") is True
        and isinstance(declared_count, int)
        and not isinstance(declared_count, bool)
        and declared_count == len(concealed)
        and concealed
        and all(tile is not None for tile in own_hand)
    )
    if not hand_trusted:
        issues.append("runtime_hand_not_fully_trusted")

    gold_components = [
        item
        for item in components
        if isinstance(item, dict)
        and (
            item.get("region_candidate") == "gold"
            or item.get("gold_skin") is True
        )
    ]
    gold_tile, gold_trusted = _trusted_gold_from_runtime(
        report,
        gold_components,
        geometry_trusted=geometry_trusted,
        issues=issues,
    )
    if not gold_trusted:
        issues.append("runtime_gold_not_fully_trusted")

    frames = report.get("frames")
    stable_frames = len(set(frames)) if isinstance(frames, (list, tuple)) else 0
    player_meld = player_meld_snapshot_from_runtime(
        report,
        timestamp_seconds=timestamp_seconds,
    )

    player_river_values, player_river_trusted = _river_values(
        player_river,
        actor="player",
        source_session=source_session,
        stream_epoch=stream_epoch,
        issues=issues,
    )
    opponent_river_values, opponent_river_trusted = _river_values(
        opponent_river,
        actor="opponent",
        source_session=source_session,
        stream_epoch=stream_epoch,
        issues=issues,
    )
    player_meld_values, player_meld_trusted = _meld_values(
        player_meld,
        actor="player",
        source_session=source_session,
        stream_epoch=stream_epoch,
        issues=issues,
    )
    opponent_meld_values, opponent_meld_trusted = _meld_values(
        opponent_meld,
        actor="opponent",
        source_session=source_session,
        stream_epoch=stream_epoch,
        issues=issues,
    )

    return CurrentTableSnapshot(
        timestamp_seconds=timestamp_seconds,
        source_session=source_session,
        stream_epoch=stream_epoch,
        stable_frames=stable_frames,
        own_hand=own_hand,
        gold_tile=gold_tile,
        rivers=(player_river_values, opponent_river_values),
        melds=(player_meld_values, opponent_meld_values),
        hand_trusted=hand_trusted,
        gold_trusted=gold_trusted,
        river_trusted=(player_river_trusted, opponent_river_trusted),
        meld_trusted=(player_meld_trusted, opponent_meld_trusted),
        adapter_issues=tuple(issues),
    )


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


def _open_meld_count_from_concealed_count(value: Any) -> int | None:
    """Infer only the exposed-meld count implied by a valid 16/17-tile hand size."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    for open_melds in range(6):
        concealed_target = (5 - open_melds) * 3 + 2
        if value in {concealed_target - 1, concealed_target}:
            return open_melds
    return None


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

    clusters = _cluster_meld_components(components)
    expected_count = _open_meld_count_from_concealed_count(
        report.get("concealed_tile_count")
    )
    preserve_count_only_incomplete = bool(
        expected_count is not None
        and expected_count == len(clusters)
        and all(2 <= len(cluster) <= 4 for cluster in clusters)
    )

    groups: list[MeldGroup] = []
    for cluster in clusters:
        if len(cluster) not in {3, 4}:
            if not preserve_count_only_incomplete:
                # Do not invent a semantic meld from weak geometry alone.
                continue
            # Concealed count and independently separated meld geometry agree
            # on the exposed-meld count. Preserve that count only; never guess
            # the missing tile identity or whether the incomplete group was a
            # chi/peng/kong. Three UNKNOWN entries represent one legal meld
            # slot for shanten structure while keeping public identity blocked.
            boxes = [_bbox(item) for item in cluster]
            groups.append(
                MeldGroup(
                    normalized_bbox=_union_bbox(boxes),
                    tiles=(None, None, None),
                    confidence=min(_component_confidence(item) for item in cluster),
                    evidence_refs=_runtime_refs(report, cluster),
                )
            )
            continue
        boxes = [_bbox(item) for item in cluster]
        groups.append(
            MeldGroup(
                normalized_bbox=_union_bbox(boxes),
                tiles=tuple(_meld_identity(item) for item in cluster),
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
