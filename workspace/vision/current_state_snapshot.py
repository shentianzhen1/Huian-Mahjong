"""Fail-closed current-table snapshot gate for advisory analysis.

The V0.1 advisory path does not need a complete action ledger.  It needs a
stable, source-qualified *current* view of the player's concealed hand, opened
Gold, public rivers and exposed melds.  This module keeps that boundary inside
Vision and deliberately does not construct Environment state or enable Hint or
Executor behavior.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from numbers import Integral

from huian._legacy import env


TileIdentity = str | None
MeldTiles = tuple[TileIdentity, ...]
ActorMelds = tuple[MeldTiles, ...]


class SnapshotCapability(str, Enum):
    SHANTEN = "SHANTEN"
    VISIBLE_REMAINDERS = "VISIBLE_REMAINDERS"
    DANGER_HINT = "DANGER_HINT"


class SnapshotStatus(str, Enum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class CurrentTableSnapshot:
    """One stable-window observation, independent of prior action history.

    ``None`` is an explicit UNKNOWN tile identity.  Trust flags describe the
    corresponding observer output; they are never inferred from non-empty
    tuples.  Seat 0 is the local player and seat 1 is the opponent.
    """

    timestamp_seconds: float
    source_session: str | None
    stream_epoch: int
    stable_frames: int
    own_hand: tuple[TileIdentity, ...]
    gold_tile: TileIdentity
    rivers: tuple[tuple[TileIdentity, ...], tuple[TileIdentity, ...]]
    melds: tuple[ActorMelds, ActorMelds]
    hand_trusted: bool
    gold_trusted: bool
    river_trusted: tuple[bool, bool]
    meld_trusted: tuple[bool, bool]
    adapter_issues: tuple[str, ...] = ()

    def __post_init__(self):
        if isinstance(self.timestamp_seconds, bool) or not isinstance(
            self.timestamp_seconds, (int, float)
        ):
            raise ValueError("timestamp_seconds must be numeric")
        if not isinstance(self.source_session, (str, type(None))):
            raise ValueError("source_session must be a string or None")
        if isinstance(self.stream_epoch, bool) or not isinstance(
            self.stream_epoch, Integral
        ):
            raise ValueError("stream_epoch must be an integer")
        if isinstance(self.stable_frames, bool) or not isinstance(
            self.stable_frames, Integral
        ):
            raise ValueError("stable_frames must be an integer")
        if len(self.rivers) != 2 or len(self.melds) != 2:
            raise ValueError("rivers and melds must contain exactly two seats")
        if len(self.river_trusted) != 2 or len(self.meld_trusted) != 2:
            raise ValueError("trust tuples must contain exactly two seats")
        object.__setattr__(
            self,
            "adapter_issues",
            tuple(str(issue) for issue in self.adapter_issues if str(issue)),
        )


@dataclass(frozen=True)
class SnapshotAssessment:
    status: SnapshotStatus
    capabilities: tuple[SnapshotCapability, ...]
    issues: tuple[str, ...]
    safe_for_executor: bool = False

    def allows(self, capability: SnapshotCapability) -> bool:
        return capability in self.capabilities


@dataclass(frozen=True)
class AdvisoryAnalysisInputs:
    own_hand: tuple[str, ...]
    gold_tile: str
    open_meld_count: int
    visible_tiles: tuple[str, ...] | None
    source_session: str
    stream_epoch: int
    safe_for_executor: bool = False


def _known_tiles(snapshot: CurrentTableSnapshot) -> tuple[str, ...]:
    tiles: list[str] = []
    for tile in snapshot.own_hand:
        if tile is not None:
            tiles.append(tile)
    for river in snapshot.rivers:
        tiles.extend(tile for tile in river if tile is not None)
    for actor_melds in snapshot.melds:
        for meld in actor_melds:
            tiles.extend(tile for tile in meld if tile is not None)
    return tuple(tiles)


def _unknown_present(groups) -> bool:
    return any(tile is None for group in groups for tile in group)


def assess_current_snapshot(
    snapshot: CurrentTableSnapshot,
    *,
    minimum_stable_frames: int = 2,
) -> SnapshotAssessment:
    """Return exactly which advisory calculations the snapshot can support."""
    if isinstance(minimum_stable_frames, bool) or not isinstance(
        minimum_stable_frames, Integral
    ) or minimum_stable_frames < 1:
        raise ValueError("minimum_stable_frames must be a positive integer")

    global_issues: list[str] = []
    shanten_issues: list[str] = []
    public_issues: list[str] = []

    if not snapshot.source_session:
        global_issues.append("source_session_missing")
    if snapshot.stream_epoch < 0:
        global_issues.append("stream_epoch_invalid")
    if snapshot.stable_frames < minimum_stable_frames:
        global_issues.append("snapshot_not_stable")

    if not snapshot.hand_trusted:
        shanten_issues.append("hand_untrusted")
    if not snapshot.own_hand or any(tile is None for tile in snapshot.own_hand):
        shanten_issues.append("hand_identity_unknown")
    if not snapshot.gold_trusted:
        shanten_issues.append("gold_untrusted")
    if snapshot.gold_tile is None:
        shanten_issues.append("gold_identity_unknown")
    if not snapshot.meld_trusted[0]:
        shanten_issues.append("player_meld_count_untrusted")

    all_known = _known_tiles(snapshot)
    invalid = tuple(sorted({tile for tile in all_known if tile not in env.BASE_TILES}))
    if snapshot.gold_tile is not None and snapshot.gold_tile not in env.BASE_TILES:
        invalid = tuple(sorted(set((*invalid, snapshot.gold_tile))))
    if invalid:
        global_issues.append("invalid_tile_identity:" + ",".join(invalid))

    counts = Counter(tile for tile in all_known if tile in env.BASE_TILES)
    overflow = tuple(sorted(tile for tile, count in counts.items() if count > 4))
    if overflow:
        global_issues.append("physical_copy_overflow:" + ",".join(overflow))
    if (
        snapshot.gold_tile in env.BASE_TILES
        and counts[snapshot.gold_tile] > 3
    ):
        global_issues.append("playable_gold_copy_overflow")

    open_melds = len(snapshot.melds[0])
    if open_melds > 5:
        global_issues.append("player_meld_count_invalid")
    elif snapshot.hand_trusted and snapshot.meld_trusted[0]:
        concealed_target = (5 - open_melds) * 3 + 2
        if len(snapshot.own_hand) not in {
            concealed_target - 1,
            concealed_target,
        }:
            shanten_issues.append("concealed_hand_count_invalid")

    for seat, trusted in enumerate(snapshot.river_trusted):
        if not trusted:
            public_issues.append(f"river_untrusted:{seat}")
        if any(tile is None for tile in snapshot.rivers[seat]):
            public_issues.append(f"river_identity_unknown:{seat}")
    for seat, trusted in enumerate(snapshot.meld_trusted):
        if not trusted:
            public_issues.append(f"meld_untrusted:{seat}")
        if _unknown_present(snapshot.melds[seat]):
            public_issues.append(f"meld_identity_unknown:{seat}")

    capabilities: list[SnapshotCapability] = []
    if not global_issues and not shanten_issues:
        capabilities.append(SnapshotCapability.SHANTEN)
        if not public_issues:
            capabilities.extend(
                (
                    SnapshotCapability.VISIBLE_REMAINDERS,
                    SnapshotCapability.DANGER_HINT,
                )
            )

    if len(capabilities) == 3:
        status = SnapshotStatus.READY
    elif capabilities:
        status = SnapshotStatus.PARTIAL
    else:
        status = SnapshotStatus.BLOCKED
    return SnapshotAssessment(
        status=status,
        capabilities=tuple(capabilities),
        issues=tuple(
            dict.fromkeys(
                (
                    *global_issues,
                    *shanten_issues,
                    *public_issues,
                    *snapshot.adapter_issues,
                )
            )
        ),
        safe_for_executor=False,
    )


def advisory_analysis_inputs(
    snapshot: CurrentTableSnapshot,
    assessment: SnapshotAssessment | None = None,
) -> AdvisoryAnalysisInputs:
    """Build immutable analysis inputs without reconstructing an action ledger."""
    result = assessment or assess_current_snapshot(snapshot)
    if not result.allows(SnapshotCapability.SHANTEN):
        raise ValueError("snapshot is not trusted for shanten analysis")

    visible_tiles: tuple[str, ...] | None = None
    if result.allows(SnapshotCapability.VISIBLE_REMAINDERS):
        values: list[str] = []
        for river in snapshot.rivers:
            values.extend(tile for tile in river if tile is not None)
        for actor_melds in snapshot.melds:
            for meld in actor_melds:
                values.extend(tile for tile in meld if tile is not None)
        visible_tiles = tuple(values)

    assert snapshot.gold_tile is not None
    assert snapshot.source_session is not None
    return AdvisoryAnalysisInputs(
        own_hand=tuple(tile for tile in snapshot.own_hand if tile is not None),
        gold_tile=snapshot.gold_tile,
        open_meld_count=len(snapshot.melds[0]),
        visible_tiles=visible_tiles,
        source_session=snapshot.source_session,
        stream_epoch=snapshot.stream_epoch,
        safe_for_executor=False,
    )
