"""Lightweight agents operating on private-hand/public-table observations."""
from .baseline import (AgentDecision, BaselineAgent, DangerAwareShantenAgent,
                       EfficiencyAgent, MatchAwareShantenAgent,
                       MatchObservationContext, MeldAwareShantenAgent,
                       PlayerObservation, ShantenAgent,
                       TenpaiLossTieBreakAgent, TenpaiRiskLossTieBreakAgent,
                       OneShantenTwoPlyRiskAgent, ScoreAwareMeldAgent,
                       ImmediateValueMeldAgent, TenpaiRiskTieBreakAgent,
                       TwoPlyShantenRiskAgent)
from .danger import PublicDangerEstimate, estimate_discard_danger
from .opponent import (OrdinaryDealInEstimate, TenpaiWaitLossEstimate,
                       TenpaiWaitRiskEstimate,
                       estimate_ordinary_deal_in_probabilities,
                       estimate_tenpai_wait_loss_scores,
                       estimate_tenpai_wait_risk_scores,
                       is_ordinary_ron_tenpai)
from .score_ev import (OrdinaryImmediateValue, OrdinaryWinningDrawValue,
                       evaluate_tenpai_ordinary_value)
from .kong import KongOpportunity, analyze_kong_actions
from .kong_agent import KongAwareMeldAgent
from .rollout import (PublicRolloutAgent, PublicRolloutEstimate,
                      estimate_public_rollouts)
from .shanten import (DiscardEfficiency, EffectiveTile, HandEfficiency,
                      TwoPlyOffense, analyze_effective_tiles,
                      analyze_two_ply_offense, best_discard, best_offense_ties,
                      min_shanten_discards, ordinary_shanten, rank_discards)

# Stable entry point for the currently promoted AI policy.
# Keep TenpaiRiskTieBreakAgent V0.6 and ShantenAgent V0.3 available explicitly
# as fixed comparison/ablation baselines.
CurrentAgent = MeldAwareShantenAgent
CURRENT_AGENT_VERSION = "v0.10"
CURRENT_AGENT_NAME = "MeldAwareShantenAgent"

__all__ = ["AgentDecision", "BaselineAgent", "EfficiencyAgent", "ShantenAgent",
           "DangerAwareShantenAgent", "MatchAwareShantenAgent",
           "MeldAwareShantenAgent",
           "TenpaiRiskTieBreakAgent", "TenpaiLossTieBreakAgent",
           "TenpaiRiskLossTieBreakAgent", "TwoPlyShantenRiskAgent",
           "OneShantenTwoPlyRiskAgent", "ScoreAwareMeldAgent",
           "ImmediateValueMeldAgent", "CurrentAgent",
           "CURRENT_AGENT_VERSION", "CURRENT_AGENT_NAME",
           "MatchObservationContext",
           "PlayerObservation",
           "DiscardEfficiency", "EffectiveTile", "HandEfficiency", "TwoPlyOffense",
           "ordinary_shanten", "analyze_effective_tiles",
           "analyze_two_ply_offense", "rank_discards",
           "best_discard", "best_offense_ties", "min_shanten_discards",
           "PublicDangerEstimate", "estimate_discard_danger",
           "OrdinaryDealInEstimate", "TenpaiWaitRiskEstimate",
           "TenpaiWaitLossEstimate",
           "estimate_ordinary_deal_in_probabilities",
           "estimate_tenpai_wait_risk_scores",
           "estimate_tenpai_wait_loss_scores", "is_ordinary_ron_tenpai",
           "OrdinaryImmediateValue", "OrdinaryWinningDrawValue",
           "evaluate_tenpai_ordinary_value", "KongOpportunity",
           "analyze_kong_actions", "KongAwareMeldAgent",
           "PublicRolloutAgent", "PublicRolloutEstimate",
           "estimate_public_rollouts"]
