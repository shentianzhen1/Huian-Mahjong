"""Fail-closed shanten bridge for a trusted current-table snapshot.

This module is advisory-only. It never builds an Environment state, never calls
CurrentAgent, and never clicks or mutates the game UI.
"""
from __future__ import annotations

from dataclasses import dataclass

from huian._legacy import env
from workspace.ai import analyze_effective_tiles, min_shanten_discards, ordinary_shanten
from workspace.vision.current_state_snapshot import (
    CurrentTableSnapshot,
    SnapshotCapability,
    advisory_analysis_inputs,
    assess_current_snapshot,
)


@dataclass(frozen=True)
class EffectiveTileHint:
    tile: str
    remaining: int
    next_shanten: int
    winning: bool


@dataclass(frozen=True)
class DiscardShantenHint:
    discard: str
    shanten: int
    total_live_copies: int | None = None
    effective_tile_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class SnapshotShantenHint:
    status: str
    allowed: bool
    phase: str | None
    shanten: int | None
    effective_tiles: tuple[EffectiveTileHint, ...]
    best_discards: tuple[DiscardShantenHint, ...]
    visible_remainders_used: bool
    issues: tuple[str, ...]
    source_session: str | None
    stream_epoch: int
    safe_for_executor: bool = False


def _tile_order(tile: str) -> int:
    return env.BASE_TILES.index(tile)


def _structural_best_discards(
    hand: tuple[str, ...],
    *,
    gold_tile: str,
    open_melds: int,
) -> tuple[DiscardShantenHint, ...]:
    values: list[tuple[str, int]] = []
    for discard in sorted(set(hand), key=_tile_order):
        reduced = list(hand)
        reduced.remove(discard)
        values.append(
            (
                discard,
                ordinary_shanten(
                    tuple(reduced),
                    gold_tile=gold_tile,
                    open_melds=open_melds,
                ),
            )
        )
    best = min(value for _, value in values)
    return tuple(
        DiscardShantenHint(discard=discard, shanten=value)
        for discard, value in values
        if value == best
    )


def analyze_snapshot_shanten(snapshot: CurrentTableSnapshot) -> SnapshotShantenHint:
    """Return only the shanten information supported by this stable snapshot."""
    assessment = assess_current_snapshot(snapshot)
    if not assessment.allows(SnapshotCapability.SHANTEN):
        return SnapshotShantenHint(
            status=assessment.status.value,
            allowed=False,
            phase=None,
            shanten=None,
            effective_tiles=(),
            best_discards=(),
            visible_remainders_used=False,
            issues=assessment.issues,
            source_session=snapshot.source_session,
            stream_epoch=snapshot.stream_epoch,
            safe_for_executor=False,
        )

    inputs = advisory_analysis_inputs(snapshot, assessment)
    hand = inputs.own_hand
    open_melds = inputs.open_meld_count
    target = (5 - open_melds) * 3 + 2
    visible_ready = (
        inputs.visible_tiles is not None
        and assessment.allows(SnapshotCapability.VISIBLE_REMAINDERS)
    )

    if len(hand) == target - 1:
        if visible_ready:
            analysis = analyze_effective_tiles(
                hand,
                gold_tile=inputs.gold_tile,
                open_melds=open_melds,
                visible_tiles=inputs.visible_tiles or (),
            )
            effective = tuple(
                EffectiveTileHint(
                    tile=item.tile,
                    remaining=item.remaining,
                    next_shanten=item.next_shanten,
                    winning=item.winning,
                )
                for item in analysis.effective_tiles
            )
            shanten = analysis.shanten
        else:
            shanten = ordinary_shanten(
                hand,
                gold_tile=inputs.gold_tile,
                open_melds=open_melds,
            )
            effective = ()
        return SnapshotShantenHint(
            status=assessment.status.value,
            allowed=True,
            phase="PRE_DRAW",
            shanten=shanten,
            effective_tiles=effective,
            best_discards=(),
            visible_remainders_used=visible_ready,
            issues=assessment.issues,
            source_session=inputs.source_session,
            stream_epoch=inputs.stream_epoch,
            safe_for_executor=False,
        )

    # A complete 17/14/11/...-tile concealed zone can already be an ordinary
    # structural win. Do not suggest a discard in that state.
    current = ordinary_shanten(
        hand,
        gold_tile=inputs.gold_tile,
        open_melds=open_melds,
    )
    if current == -1:
        return SnapshotShantenHint(
            status=assessment.status.value,
            allowed=True,
            phase="POST_DRAW_COMPLETE",
            shanten=-1,
            effective_tiles=(),
            best_discards=(),
            visible_remainders_used=visible_ready,
            issues=assessment.issues,
            source_session=inputs.source_session,
            stream_epoch=inputs.stream_epoch,
            safe_for_executor=False,
        )

    if visible_ready:
        frontier = min_shanten_discards(
            hand,
            gold_tile=inputs.gold_tile,
            open_melds=open_melds,
            visible_tiles=inputs.visible_tiles or (),
        )
        discards = tuple(
            DiscardShantenHint(
                discard=item.discard,
                shanten=item.shanten,
                total_live_copies=item.total_live_copies,
                effective_tile_types=item.effective_tile_types,
            )
            for item in frontier
        )
    else:
        discards = _structural_best_discards(
            hand,
            gold_tile=inputs.gold_tile,
            open_melds=open_melds,
        )

    return SnapshotShantenHint(
        status=assessment.status.value,
        allowed=True,
        phase="POST_DRAW",
        shanten=discards[0].shanten if discards else current,
        effective_tiles=(),
        best_discards=discards,
        visible_remainders_used=visible_ready,
        issues=assessment.issues,
        source_session=inputs.source_session,
        stream_epoch=inputs.stream_epoch,
        safe_for_executor=False,
    )
