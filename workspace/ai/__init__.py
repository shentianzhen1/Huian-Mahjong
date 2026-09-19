"""Lightweight agents operating on private-hand/public-table observations."""
from .baseline import (AgentDecision, BaselineAgent, DangerAwareShantenAgent,
                       EfficiencyAgent, MatchAwareShantenAgent,
                       MatchObservationContext, PlayerObservation, ShantenAgent,
                       TenpaiLossTieBreakAgent, TenpaiRiskTieBreakAgent)
from .danger import PublicDangerEstimate, estimate_discard_danger
from .opponent import (OrdinaryDealInEstimate, TenpaiWaitLossEstimate,
                       TenpaiWaitRiskEstimate,
                       estimate_ordinary_deal_in_probabilities,
                       estimate_tenpai_wait_loss_scores,
                       estimate_tenpai_wait_risk_scores)
from .shanten import (DiscardEfficiency, EffectiveTile, HandEfficiency,
                      analyze_effective_tiles, best_discard, best_offense_ties,
                      min_shanten_discards, ordinary_shanten, rank_discards)

# Stable entry point for the currently promoted AI policy.
# Keep ShantenAgent available explicitly as the V0.3 comparison baseline.
CurrentAgent = TenpaiRiskTieBreakAgent
CURRENT_AGENT_VERSION = "v0.6"
CURRENT_AGENT_NAME = "TenpaiRiskTieBreakAgent"

__all__ = ["AgentDecision", "BaselineAgent", "EfficiencyAgent", "ShantenAgent",
           "DangerAwareShantenAgent", "MatchAwareShantenAgent",
           "TenpaiRiskTieBreakAgent", "TenpaiLossTieBreakAgent", "CurrentAgent",
           "CURRENT_AGENT_VERSION", "CURRENT_AGENT_NAME",
           "MatchObservationContext",
           "PlayerObservation",
           "DiscardEfficiency", "EffectiveTile", "HandEfficiency",
           "ordinary_shanten", "analyze_effective_tiles", "rank_discards",
           "best_discard", "best_offense_ties", "min_shanten_discards",
           "PublicDangerEstimate", "estimate_discard_danger",
           "OrdinaryDealInEstimate", "TenpaiWaitRiskEstimate",
           "TenpaiWaitLossEstimate",
           "estimate_ordinary_deal_in_probabilities",
           "estimate_tenpai_wait_risk_scores",
           "estimate_tenpai_wait_loss_scores"]
