"""Incremental Huian rules integration; legacy entry points remain unchanged."""
from .rules import (DrawSource, FanAggregator, FanComponent, FanResult, HuContext, HuDecomposition, HuianRules,
                    HuianRulesAdapter, HuResult, KongFanResult, KongKind, RulesConfig,
                    SanjindaoChoice, SanjindaoDecision, SPECIAL_OUTCOMES,
                    SpecialOutcomeProfile, UnknownRuleError, WinSource,
                    YoujinOfferRule, YoujinOpponentResponseRule, YoujinScoreTerms,
                    YoujinStage, special_outcome_profile, youjin_offer_rule,
                    youjin_opponent_response_rule)
from .environment import HuianGameState, HuianEnvironment, DeadLoopError

__all__ = ["DrawSource", "FanAggregator", "FanComponent", "FanResult", "HuContext", "HuDecomposition", "HuianRules",
           "HuianRulesAdapter", "HuResult", "KongFanResult", "KongKind", "RulesConfig",
           "SanjindaoChoice", "SanjindaoDecision", "UnknownRuleError", "WinSource",
           "YoujinOfferRule", "YoujinOpponentResponseRule", "YoujinScoreTerms",
           "YoujinStage", "youjin_offer_rule", "youjin_opponent_response_rule",
           "SPECIAL_OUTCOMES",
           "SpecialOutcomeProfile", "special_outcome_profile",
           "HuianGameState", "HuianEnvironment",
           "DeadLoopError"]
