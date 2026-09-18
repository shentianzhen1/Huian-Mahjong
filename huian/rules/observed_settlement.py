"""Evidence-scoped Huian two-player ordinary settlement plugin.

Only ordinary Pinghu and Zimo are enabled because direct settlement evidence
covers those two outcomes. The same confirmed formula serves both externally
observed outcomes and FanAggregator-complete automatic ordinary settlement.
Special wins, kong side payments and flow settlement remain outside this plugin.
"""
from dataclasses import dataclass

from mahjong_framework import MahjongSettlementPlugin
from .config import EvidenceStatus, UnknownRuleError
from .engine import nonnegative_int


@dataclass(frozen=True)
class HuianObservedSettlement:
    rewards: tuple[int, int]
    current_dealer_base: int
    winner_fan: int
    win_type: str
    multiplier: int
    status: EvidenceStatus = EvidenceStatus.CONFIRMED
    evidence: str = "WGC captures 2026-09-13: Pinghu +11/+16 and Zimo x2 +38"


class HuianObservedSettlementPlugin(MahjongSettlementPlugin):
    """Settlement formula for evidence-confirmed ordinary Pinghu/Zimo outcomes."""

    variant_id = "huian.two_player.v0_1"
    _MULTIPLIERS = {"PINGHU": 1, "ZIMO": 2}

    def settle(self, *, winner, current_dealer_base, winner_fan, win_type):
        if win_type not in self._MULTIPLIERS:
            raise UnknownRuleError("settlement_" + str(win_type).lower())
        for name, value in (("winner", winner), ("current_dealer_base", current_dealer_base),
                            ("winner_fan", winner_fan)):
            nonnegative_int(value, name)
        if winner not in (0, 1):
            raise ValueError("winner must be seat 0 or 1")
        multiplier = self._MULTIPLIERS[win_type]
        net = (current_dealer_base + winner_fan) * multiplier
        rewards = (net, -net) if winner == 0 else (-net, net)
        return HuianObservedSettlement(rewards, current_dealer_base, winner_fan,
                                       win_type, multiplier)