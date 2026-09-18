"""Incremental Huian rules integration; legacy entry points remain unchanged."""
from .rules import (DrawSource, FanAggregator, FanComponent, FanResult, HuContext, HuDecomposition, HuianRules,
                    HuianRulesAdapter, HuResult, KongFanResult, KongKind, RulesConfig,
                    SanjindaoChoice, SanjindaoDecision, SPECIAL_OUTCOMES,
                    SpecialOutcomeProfile, UnknownRuleError, WinSource,
                    YoujinScoreTerms, YoujinStage, special_outcome_profile)
from .environment import HuianGameState, HuianEnvironment, DeadLoopError

__all__ = ["DrawSource", "FanAggregator", "FanComponent", "FanResult", "HuContext", "HuDecomposition", "HuianRules",
           "HuianRulesAdapter", "HuResult", "KongFanResult", "KongKind", "RulesConfig",
           "SanjindaoChoice", "SanjindaoDecision", "UnknownRuleError", "WinSource",
           "YoujinScoreTerms", "YoujinStage", "SPECIAL_OUTCOMES",
           "SpecialOutcomeProfile", "special_outcome_profile",
           "HuianGameState", "HuianEnvironment",
           "DeadLoopError"]
