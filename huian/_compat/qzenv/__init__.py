"""Private minimum environment compatibility surface.

This module intentionally exposes only the types/constants still used by the
current Huian implementation. The historical qzenv package remains under
legacy_code for comparison tests only.
"""
from .tiles import *
from .actions import Action, ActionType
from .events import Event
from .state import GameState, Meld
from .rules_adapter import RulesAdapter, ScaffoldRules
from .environment import QuanzhouEnvironment

__all__ = [
    "Action", "ActionType", "Event", "GameState", "Meld",
    "RulesAdapter", "ScaffoldRules", "QuanzhouEnvironment",
    "SUITS", "HONORS", "FLOWERS", "BASE_TILES", "CN",
    "full_wall", "validate_multiset",
]
