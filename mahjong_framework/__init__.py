"""Ruleset-neutral framework contracts.

Concrete variants live outside this package, for example ``huian``.
"""
from .contracts import MahjongOpeningPlugin, MahjongRulesPlugin

__all__ = ["MahjongOpeningPlugin", "MahjongRulesPlugin"]