"""Incremental Huian rules integration; legacy entry points remain unchanged."""
from .version import PROJECT_NAME, PROJECT_VERSION, project_manifest
from .rules import (DrawSource, FanAggregator, FanComponent, FanResult, HuContext, HuDecomposition, HuianRules,
                    HuianRulesAdapter, HuResult, KongFanResult, KongKind, RulesConfig,
                    SanjindaoChoice, SanjindaoDecision, SPECIAL_OUTCOMES,
                    SpecialOutcomeProfile, UnknownRuleError, WinSource,
                    YoujinOfferRule, YoujinOpponentResponseRule,
                    YoujinProgressionRule, YoujinScoreTerms,
                    YoujinStage, special_outcome_profile, youjin_offer_rule,
                    youjin_opponent_response_rule, youjin_progression_rule)
from .environment import HuianGameState, HuianEnvironment, DeadLoopError

__version__ = PROJECT_VERSION

__all__ = ["PROJECT_NAME", "PROJECT_VERSION", "__version__", "project_manifest", "DrawSource", "FanAggregator", "FanComponent", "FanResult", "HuContext", "HuDecomposition", "HuianRules",
           "HuianRulesAdapter", "HuResult", "KongFanResult", "KongKind", "RulesConfig",
           "SanjindaoChoice", "SanjindaoDecision", "UnknownRuleError", "WinSource",
           "YoujinOfferRule", "YoujinOpponentResponseRule",
           "YoujinProgressionRule", "YoujinScoreTerms",
           "YoujinStage", "youjin_offer_rule", "youjin_opponent_response_rule",
           "youjin_progression_rule",
           "SPECIAL_OUTCOMES",
           "SpecialOutcomeProfile", "special_outcome_profile",
           "HuianGameState", "HuianEnvironment",
           "DeadLoopError"]
