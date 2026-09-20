"""CurrentAgent bridge protected by the Hint Alpha fail-closed gate."""
from dataclasses import dataclass

from workspace.ai import (
    CURRENT_AGENT_NAME,
    CURRENT_AGENT_VERSION,
    CurrentAgent,
)

from .safety import AdvisoryGate, AdvisoryState


@dataclass(frozen=True)
class HintDecision:
    state: str
    allowed: bool
    action_type: str | None
    tile: str | None
    reason: str
    agent_name: str = CURRENT_AGENT_NAME
    agent_version: str = CURRENT_AGENT_VERSION
    rule_snapshot_id: str | None = None


def _action_fields(action):
    action_type = getattr(getattr(action, "type", None), "value", None)
    if action_type is None:
        action_type = str(getattr(action, "type", "")) or None
    return action_type, getattr(action, "tile", None)


class HintAdvisor:
    """Advisory-only CurrentAgent wrapper; never mutates Environment or UI."""

    def __init__(self, agent=None, gate=None):
        self.agent = agent if agent is not None else CurrentAgent()
        self.gate = gate if gate is not None else AdvisoryGate()

    def recommend(
        self,
        observation,
        legal_actions,
        *,
        vision_confidence,
        vision_issues=(),
        unresolved_rules=(),
        required_rules=(),
    ):
        actions = tuple(legal_actions or ())
        gate = self.gate.evaluate(
            vision_confidence=vision_confidence,
            vision_issues=vision_issues,
            unresolved_rules=unresolved_rules,
            required_rules=required_rules,
            has_legal_actions=bool(actions),
        )
        if not gate.allowed:
            return HintDecision(
                state=gate.state.value,
                allowed=False,
                action_type=None,
                tile=None,
                reason=gate.display_text,
                rule_snapshot_id=gate.rule_snapshot_id,
            )

        try:
            decision = self.agent.choose_decision(observation, actions)
            action_type, tile = _action_fields(decision.action)
            return HintDecision(
                state=AdvisoryState.READY.value,
                allowed=True,
                action_type=action_type,
                tile=tile,
                reason=decision.reason,
                rule_snapshot_id=gate.rule_snapshot_id,
            )
        except Exception as exc:
            return HintDecision(
                state=AdvisoryState.ERROR.value,
                allowed=False,
                action_type=None,
                tile=None,
                reason=f"提示计算失败：{type(exc).__name__}: {exc}",
                rule_snapshot_id=gate.rule_snapshot_id,
            )
