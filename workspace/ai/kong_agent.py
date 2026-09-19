"""Experimental kong-aware policy kept separate from the promoted agent."""
from huian._legacy import env

from .baseline import AgentDecision, MeldAwareShantenAgent
from .kong import analyze_kong_actions


class KongAwareMeldAgent(MeldAwareShantenAgent):
    """V0.13 candidate: take only unblocked, ordinary-shape-neutral kongs.

    This is an experiment, not the project default.  It never takes ADD_KONG,
    never acts while a gold-related special path is visible, and never acts
    when the ordinary projection sees a possible kong-tail Hu.
    """

    VERSION = "v0.13-kong-shadow"

    @staticmethod
    def _candidate_key(item):
        # Prefer the higher adopted fan, then concealed over exposed, then tile
        # order supplied by the deterministic action sort in analyze_kong_actions.
        return (item.kong_fan, item.action_type == "AN_GANG", item.tile)

    def choose_decision(self, observation, legal_actions):
        base = super().choose_decision(observation, legal_actions)
        if base.action.type in (
                env.ActionType.HU, env.ActionType.ROB_KONG_HU,
                env.ActionType.CHI, env.ActionType.PENG):
            return base
        if (observation.gold_tile is not None
                and observation.gold_tile in observation.hand):
            return base

        opportunities = analyze_kong_actions(observation, legal_actions)
        eligible = [item for item in opportunities
                    if item.action_type in ("AN_GANG", "MING_GANG")
                    and item.structural_relation == "EQUAL"
                    and not item.blockers]
        if not eligible:
            return base
        # If V0.10 already found a strict Chi/Peng improvement, preserve it.
        if base.action.type not in (env.ActionType.DISCARD, env.ActionType.PASS):
            return base

        chosen = max(eligible, key=self._candidate_key)
        action = next(
            action for action in legal_actions
            if action.type.value == chosen.action_type and action.tile == chosen.tile
        )
        return AgentDecision(
            action,
            f"{chosen.action_type} {chosen.tile}: kong_v0.13_shadow "
            f"ordinary structure equal to {chosen.baseline_mode.lower()} "
            f"(shanten={chosen.post_kong_shanten},"
            f"live={chosen.post_kong_live_copies},"
            f"types={chosen.post_kong_effective_types}); "
            f"confirmed_fan={chosen.kong_fan}; no unresolved blocker",
        )
