"""Confirmed two-player flow overlay.

Player feedback establishes that these transitions follow Quanzhou flow.  This
module intentionally does not add a four-player scoring model or special-hand
logic.
"""
from huian._legacy import env
from huian.rules.adapter import HuianRulesAdapter
from huian.rules.phases import ActionReport
from .engine import HuianEnvironment


class HuianConfirmedFlowAdapter(HuianRulesAdapter):
    """Expose the confirmed PASS and 16-wall transitions as known actions."""
    def action_report(self, state):
        if not state.terminal and state.phase == "NEED_DRAW" and len(state.wall) <= 16:
            return ActionReport((env.Action(
                state.current_player, env.ActionType.END_HAND,
                metadata={"reason": "wall_boundary"},
            ),))
        result = super().action_report(state)
        if not state.terminal and state.phase == "AFTER_DISCARD":
            known = tuple(result.known_actions) + (
                env.Action(state.current_player, env.ActionType.PASS),
            )
            unresolved = tuple(rule for rule in result.unresolved if rule != "pass_transition")
            return ActionReport(known, unresolved)
        return result

    def authorize_action(self, state, action):
        report = self.action_report(state)
        if action in report.known_actions:
            return
        return super().authorize_action(state, action)


class HuianConfirmedFlowEnvironment(HuianEnvironment):
    """Environment with only the player-confirmed shared-flow transitions."""
    def __init__(self, rules=None, max_steps=10000):
        super().__init__(rules or HuianConfirmedFlowAdapter(), max_steps=max_steps)

    @staticmethod
    def _apply(state, action):
        if action.type == env.ActionType.PASS:
            state.pending_discard = None
            if len(state.wall) <= 16:
                state.terminal = True
                state.rewards = [0, 0]
                state.phase = "TERMINAL"
            else:
                state.phase = "NEED_DRAW"
            return
        if action.type == env.ActionType.END_HAND:
            if action.metadata != {"reason": "wall_boundary"} or len(state.wall) > 16:
                raise ValueError("END_HAND is reserved for the confirmed wall boundary")
            state.pending_discard = None
            state.terminal = True
            state.rewards = [0, 0]
            state.phase = "TERMINAL"
            return
        HuianEnvironment._apply(state, action)
