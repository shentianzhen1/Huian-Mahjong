"""Immutable result/value models used by the Huian rules engine.

These classes contain no phase dispatch or mutable game-state transitions.
They are split from engine.py so the rule engine can remain focused on behavior.
"""
from dataclasses import dataclass

from .config import EvidenceStatus
from .context import HuContext, KongKind, YoujinStage
from .values import nonnegative_int


@dataclass(frozen=True)
class Settlement:
    rewards: tuple[int, int]
    current_dealer_base: int
    winner_fan: int
    multiplier: int
    status: EvidenceStatus = EvidenceStatus.HIGH_CONFIDENCE
    evidence: str = "RULE_STATUS.md: settlement examples A/B; third example pending"


@dataclass(frozen=True)
class HuDecomposition:
    """One structural ordinary-Hu split; GOLD denotes a wildcard position."""

    pair: tuple[str, str]
    groups: tuple[tuple[str, str, str], ...]

    @property
    def gold_used(self):
        return self.pair.count("GOLD") + sum(
            group.count("GOLD") for group in self.groups
        )


@dataclass(frozen=True)
class HuResult:
    """Structural Hu analysis only; fan and settlement remain separate concerns."""

    legal: bool
    decompositions: tuple[HuDecomposition, ...]
    gold_tile: str | None
    open_melds: int
    context: HuContext
    may_be_truncated: bool = False

    @property
    def win_source(self):
        return self.context.source

    @property
    def winning_tile(self):
        return self.context.winning_tile

    @property
    def kong_kind(self):
        return self.context.kong_kind

    @property
    def is_gang_hu(self):
        return self.context.is_gang_hu


@dataclass(frozen=True)
class YoujinMeldDecomposition:
    """One meld-only split after reserving exactly one roaming Jin."""

    groups: tuple[tuple[str, str, str], ...]

    @property
    def gold_used(self):
        return sum(group.count("GOLD") for group in self.groups)


@dataclass(frozen=True)
class YoujinMeldResult:
    """Structural Youjin meld analysis without fan/settlement assumptions."""

    legal: bool
    decompositions: tuple[YoujinMeldDecomposition, ...]
    gold_tile: str | None
    open_melds: int
    may_be_truncated: bool = False


@dataclass(frozen=True)
class KongFanResult:
    """Adopted kong fan value with its evidence grade."""

    kind: KongKind
    tile: str
    fan: int
    status: EvidenceStatus
    evidence: str


@dataclass(frozen=True)
class YoujinScoreTerms:
    """Confirmed target-room factors without inferring base or payer."""

    stage: YoujinStage
    youjin_multiplier: int
    dealer_multiplier: int
    winner_fan: int

    def total_for_current_dealer_base(self, current_dealer_base):
        nonnegative_int(current_dealer_base, "current_dealer_base")
        return (
            (current_dealer_base + self.winner_fan)
            * self.youjin_multiplier
            * self.dealer_multiplier
        )
