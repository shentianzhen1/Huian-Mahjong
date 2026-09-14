"""Incremental Huian rules integration; legacy entry points remain unchanged."""
from .rules import (DrawSource, HuContext, HuDecomposition, HuianRules,
                    HuianRulesAdapter, HuResult, KongKind, RulesConfig,
                    SanjindaoChoice, SanjindaoDecision, UnknownRuleError,
                    WinSource)
from .environment import HuianGameState, HuianEnvironment, DeadLoopError

__all__ = ["DrawSource", "HuContext", "HuDecomposition", "HuianRules",
           "HuianRulesAdapter", "HuResult", "KongKind", "RulesConfig",
           "SanjindaoChoice", "SanjindaoDecision", "UnknownRuleError", "WinSource",
           "HuianGameState", "HuianEnvironment", "DeadLoopError"]
