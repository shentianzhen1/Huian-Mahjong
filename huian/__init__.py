"""Incremental Huian rules integration; legacy entry points remain unchanged."""
from .rules import (DrawSource, HuContext, HuDecomposition, HuianRules,
                    HuianRulesAdapter, HuResult, KongFanResult, KongKind, RulesConfig,
                    SanjindaoChoice, SanjindaoDecision, UnknownRuleError,
                    WinSource, YoujinScoreTerms, YoujinStage)
from .environment import HuianGameState, HuianEnvironment, DeadLoopError

__all__ = ["DrawSource", "HuContext", "HuDecomposition", "HuianRules",
           "HuianRulesAdapter", "HuResult", "KongFanResult", "KongKind", "RulesConfig",
           "SanjindaoChoice", "SanjindaoDecision", "UnknownRuleError", "WinSource",
           "YoujinScoreTerms", "YoujinStage", "HuianGameState", "HuianEnvironment",
           "DeadLoopError"]
