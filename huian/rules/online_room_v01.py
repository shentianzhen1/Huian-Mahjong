"""Explicit, evidence-labelled Huian online-room V0.1 profile.

This profile is opt-in.  It captures player-confirmed overrides and a small set
of high-confidence flow assumptions without changing the conservative base
RulesConfig defaults.
"""
from dataclasses import dataclass

from huian._legacy import env
from .config import EvidenceStatus


@dataclass(frozen=True)
class HuianOnlineRoomV01:
    """Rules needed by the next complete-game simulator milestone."""
    base_wall_reserve: int = 16
    dynamic_kong_reserve: bool = True

    # Target-room player feedback / recorded evidence.
    allow_chi: bool = True
    single_gold_only: bool = True
    discard_gold_can_hu: bool = False
    zimo_multiplier: int = 2

    def __post_init__(self):
        if type(self.base_wall_reserve) is not int or self.base_wall_reserve < 0:
            raise ValueError("base_wall_reserve must be a nonnegative integer")
        for value in (self.dynamic_kong_reserve, self.allow_chi,
                      self.single_gold_only, self.discard_gold_can_hu):
            if type(value) is not bool:
                raise ValueError("room profile switches must be boolean")

    def gold_tiles(self, indicator):
        """Target-room feedback confirms one indicator tile type, not ±1 golds."""
        if indicator not in env.BASE_TILES:
            raise ValueError("Gold indicator must be a normal tile")
        return frozenset((indicator,))

    def wall_reserve(self, melds_by_player):
        """V0.1 high-confidence dynamic reserve; can be disabled for comparison."""
        if len(melds_by_player) != 2:
            raise ValueError("Two players are required")
        ming, an = 0, 0
        for player_melds in melds_by_player:
            for meld in player_melds:
                kind = getattr(meld, "kind", meld)
                ming += kind == env.ActionType.MING_GANG.value
                an += kind == env.ActionType.AN_GANG.value
        if not self.dynamic_kong_reserve:
            return self.base_wall_reserve
        return self.base_wall_reserve + ming + an * 2

    def is_wall_draw(self, wall_remaining, melds_by_player):
        if type(wall_remaining) is not int or wall_remaining < 0:
            raise ValueError("wall_remaining must be a nonnegative integer")
        return wall_remaining <= self.wall_reserve(melds_by_player)

    def may_claim_discard(self, action_type, discard, indicator):
        """Gold discards cannot be claimed by any target-room action."""
        if discard in self.gold_tiles(indicator):
            return False
        return action_type in {
            env.ActionType.CHI, env.ActionType.PENG, env.ActionType.MING_GANG,
            env.ActionType.HU,
        }

    @property
    def evidence_status(self):
        return {
            "allow_chi": EvidenceStatus.CONFIRMED,
            "single_gold_only": EvidenceStatus.CONFIRMED,
            "discard_gold_can_hu": EvidenceStatus.CONFIRMED,
            "zimo_multiplier": EvidenceStatus.CONFIRMED,
            "dealer_first_flower_rounds": EvidenceStatus.HIGH_CONFIDENCE,
            "dynamic_kong_reserve": EvidenceStatus.WORKING,
        }
