"""Public-only danger hints for a trusted current-table snapshot.

The result is a transparent exposure proxy, not a deal-in probability. It is
available only when the snapshot has complete trusted public rivers and meld
identities. Gold discard is intentionally excluded because it can enter
special Youjin state and must not be treated as an ordinary discard.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from huian._legacy import env
from workspace.ai import estimate_discard_danger
from workspace.vision.current_state_snapshot import (
    CurrentTableSnapshot,
    SnapshotCapability,
    assess_current_snapshot,
)


@dataclass(frozen=True)
class SnapshotDangerItem:
    tile: str
    risk_units: int
    unseen_copies: int
    own_copies: int
    public_copies: int
    opponent_discard_copies: int
    is_probability: bool = False


@dataclass(frozen=True)
class SnapshotDangerHint:
    status: str
    allowed: bool
    items: tuple[SnapshotDangerItem, ...]
    unsupported_tiles: tuple[str, ...]
    issues: tuple[str, ...]
    source_session: str | None
    stream_epoch: int
    safe_for_executor: bool = False


def _tile_order(tile: str) -> int:
    return env.BASE_TILES.index(tile)


def analyze_snapshot_danger(
    snapshot: CurrentTableSnapshot,
    candidate_tiles: tuple[str, ...] | None = None,
) -> SnapshotDangerHint:
    """Return deterministic public-exposure risk units for discard candidates."""
    assessment = assess_current_snapshot(snapshot)
    if not assessment.allows(SnapshotCapability.DANGER_HINT):
        return SnapshotDangerHint(
            status=assessment.status.value,
            allowed=False,
            items=(),
            unsupported_tiles=(),
            issues=assessment.issues,
            source_session=snapshot.source_session,
            stream_epoch=snapshot.stream_epoch,
            safe_for_executor=False,
        )

    open_melds = len(snapshot.melds[0])
    target = (5 - open_melds) * 3 + 2
    if len(snapshot.own_hand) != target:
        return SnapshotDangerHint(
            status=assessment.status.value,
            allowed=False,
            items=(),
            unsupported_tiles=(),
            issues=tuple(dict.fromkeys((*assessment.issues, "discard_window_not_observed"))),
            source_session=snapshot.source_session,
            stream_epoch=snapshot.stream_epoch,
            safe_for_executor=False,
        )

    assert all(tile is not None for tile in snapshot.own_hand)
    hand = tuple(tile for tile in snapshot.own_hand if tile is not None)
    requested = (
        tuple(sorted(set(hand), key=_tile_order))
        if candidate_tiles is None
        else tuple(dict.fromkeys(candidate_tiles))
    )
    if not requested:
        raise ValueError("candidate_tiles must be nonempty when provided")
    for tile in requested:
        if tile not in env.BASE_TILES:
            raise ValueError("danger candidates must be base tiles")
        if tile not in hand:
            raise ValueError("danger candidate must be present in own hand")

    unsupported = tuple(tile for tile in requested if tile == snapshot.gold_tile)
    supported = tuple(tile for tile in requested if tile != snapshot.gold_tile)

    # estimate_discard_danger only consumes these four public/private fields.
    # Preserve the existing AI metric without inventing Environment state.
    observation = SimpleNamespace(
        seat=0,
        hand=hand,
        discards=tuple(tuple(tile for tile in river if tile is not None)
                       for river in snapshot.rivers),
        melds=tuple(
            tuple(("OBSERVED", tuple(tile for tile in meld if tile is not None))
                  for meld in actor_melds)
            for actor_melds in snapshot.melds
        ),
    )
    estimates = tuple(
        estimate_discard_danger(observation, tile)
        for tile in supported
    )
    items = tuple(
        SnapshotDangerItem(
            tile=item.tile,
            risk_units=item.risk_units,
            unseen_copies=item.unseen_copies,
            own_copies=item.own_copies,
            public_copies=item.public_copies,
            opponent_discard_copies=item.opponent_discard_copies,
            is_probability=False,
        )
        for item in sorted(
            estimates,
            key=lambda value: (value.risk_units, _tile_order(value.tile)),
        )
    )
    issues = list(assessment.issues)
    if unsupported:
        issues.append("gold_discard_special_state_unsupported")
    return SnapshotDangerHint(
        status=assessment.status.value,
        allowed=bool(items),
        items=items,
        unsupported_tiles=unsupported,
        issues=tuple(dict.fromkeys(issues)),
        source_session=snapshot.source_session,
        stream_epoch=snapshot.stream_epoch,
        safe_for_executor=False,
    )
