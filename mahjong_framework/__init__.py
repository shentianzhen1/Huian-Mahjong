"""Ruleset-neutral framework contracts.

Concrete variants live outside this package, for example ``huian``.
"""
from .contracts import MahjongOpeningPlugin, MahjongRulesPlugin, MahjongSettlementPlugin

__all__ = ["MahjongOpeningPlugin", "MahjongRulesPlugin", "MahjongSettlementPlugin"]